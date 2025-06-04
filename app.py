from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Book, Genre, Cover, Review, Collection
from forms import LoginForm, BookForm, ReviewForm, CollectionForm
import os
import hashlib
import markdown
from bleach import clean

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/covers'

# --- Init ---
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Для выполнения данного действия необходимо пройти процедуру аутентификации.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Главная с пагинацией ---
@app.route('/')
@app.route('/page/<int:page>')
def index(page=1):
    per_page = 6
    books = Book.query.order_by(Book.year.desc()).paginate(page=page, per_page=per_page)
    return render_template('index.html', books=books)

# --- Просмотр книги ---
@app.route('/book/<int:book_id>')
def view_book(book_id):
    book = Book.query.get_or_404(book_id)
    reviews = Review.query.filter_by(book_id=book_id).order_by(Review.timestamp.desc()).all()

    user_review = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()

    review_form = ReviewForm()           # форма для рецензии
    collection_form = CollectionForm()   # форма для добавления в подборку

    return render_template('view_book.html', book=book, reviews=reviews, user_review=user_review, review_form=review_form, collection_form=collection_form)

# --- Добавление рецензии ---
@app.route('/review/<int:book_id>', methods=['POST'])
@login_required
def add_review(book_id):
    book = Book.query.get_or_404(book_id)
    form = ReviewForm()

    # Проверка: не оставлял ли пользователь уже рецензию на эту книгу
    existing_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()
    if existing_review:
        flash('Вы уже оставили рецензию на эту книгу.', 'warning')
        return redirect(url_for('view_book', book_id=book_id))

    if form.validate_on_submit():
        print('Форма прошла валидацию!')  # Лог в консоль
        review = Review(
            text=form.text.data,
            rating=form.rating.data,
            user_id=current_user.id,
            book_id=book_id
        )
        db.session.add(review)
        db.session.commit()
        flash('Рецензия добавлена!', 'success')
        return redirect(url_for('view_book', book_id=book_id))
    else:
        if request.method == 'POST':
            print('Форма НЕ прошла валидацию.')
            print(form.errors)

    return render_template('review_form.html', form=form, book=book)

# --- Мои подборки ---
@app.route('/collections', methods=['GET', 'POST'])
@login_required
def collections():
    form = CollectionForm()
    if form.validate_on_submit():
        new_collection = Collection(name=form.name.data, user_id=current_user.id)
        db.session.add(new_collection)
        db.session.commit()
        flash('Подборка добавлена', 'success')
        return redirect(url_for('collections'))
    collections = Collection.query.filter_by(user_id=current_user.id).all()
    return render_template('collections.html', collections=collections, form=form)

@app.route('/collections/<int:collection_id>')
@login_required
def view_collection(collection_id):
    collection = Collection.query.filter_by(id=collection_id, user_id=current_user.id).first_or_404()
    return render_template('collection_books.html', collection=collection)

# --- Добавление подборки ---
@app.route('/add_to_collection/<int:book_id>', methods=['POST'])
@login_required
def add_to_collection(book_id):
    from models import Collection, Book  # если нужно, добавь импорт наверх

    # Получаем ID подборки из формы
    collection_id = request.form.get('collection_id')
    
    # Ищем подборку текущего пользователя
    collection = Collection.query.filter_by(id=collection_id, user_id=current_user.id).first()
    
    if not collection:
        flash('Подборка не найдена или не принадлежит вам.', 'danger')
        return redirect(url_for('view_book', book_id=book_id))
    
    # Ищем книгу
    book = Book.query.get_or_404(book_id)
    
    # Проверяем, есть ли книга уже в подборке
    if book in collection.books:
        flash('Книга уже есть в подборке.', 'info')
    else:
        collection.books.append(book)
        db.session.commit()
        flash('Книга успешно добавлена в подборку.', 'success')
    
    return redirect(url_for('view_book', book_id=book_id))

# --- Добавление книги ---
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_book():
    print(f"Метод: {request.method}")

    # Проверка прав
    if current_user.role.name != 'Администратор':
        flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
        print("Пользователь не админ!")
        return redirect(url_for('index'))

    form = BookForm()
    form.genres.choices = [(g.id, g.name) for g in Genre.query.all()]  # список жанров в форме

    if form.validate_on_submit():
        print("Форма прошла валидацию!")

        # Создание новой книги
        book = Book(
            title=form.title.data,
            description=form.description.data,
            year=form.year.data,
            publisher=form.publisher.data,
            author=form.author.data,
            pages=form.pages.data
        )

        # Связывание жанров
        selected_genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()
        book.genres = selected_genres

        db.session.add(book)
        db.session.commit()

        # Обработка обложки
        if form.cover.data:
            file = form.cover.data
            content = file.read()
            md5 = hashlib.md5(content).hexdigest()

            existing_cover = Cover.query.filter_by(md5_hash=md5).first()
            if existing_cover:
                book.cover = existing_cover
            else:
                filename = f"{book.id}_{secure_filename(file.filename)}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                with open(file_path, 'wb') as f:
                    f.write(content)
                new_cover = Cover(filename=filename, mimetype=file.mimetype, md5_hash=md5, book=book)
                db.session.add(new_cover)

        db.session.commit()

        flash('Книга успешно добавлена!', 'success')
        return redirect(url_for('index'))
    else:
        if request.method == 'POST':
            print("Форма НЕ прошла валидацию.")
            print(form.errors)  # вывод ошибок в консоль

    return render_template('book_form.html', form=form, show_cover_field=True)

# --- Редактирование книги ---
@app.route('/edit/<int:book_id>', methods=['GET', 'POST'])
@login_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    if current_user.role.name not in ['Администратор', 'Модератор']:
        flash('У вас недостаточно прав.', 'danger')
        return redirect(url_for('index'))

    form = BookForm(obj=book)
    form.genres.choices = [(g.id, g.name) for g in Genre.query.all()]

    if request.method == 'GET':
        form.genres.data = [g.id for g in book.genres]

    if form.validate_on_submit():
        book.title = form.title.data
        book.description = form.description.data
        book.year = form.year.data
        book.publisher = form.publisher.data
        book.author = form.author.data
        book.pages = form.pages.data
        book.genres = Genre.query.filter(Genre.id.in_(form.genres.data)).all()

        db.session.commit()
        flash('Книга обновлена', 'success')
        return redirect(url_for('view_book', book_id=book.id))

    return render_template('book_form.html', form=form, title='Редактировать книгу', show_cover_field=False)

# --- Удаление книги ---
@app.route('/delete/<int:book_id>', methods=['POST'])
@login_required
def delete_book(book_id):
    if current_user.role.name != 'Администратор':
        flash('У вас недостаточно прав для выполнения данного действия.', 'danger')
        return redirect(url_for('index'))
    book = Book.query.get_or_404(book_id)
    if book.cover:
        cover_path = os.path.join(app.config['UPLOAD_FOLDER'], book.cover.filename)
        if os.path.exists(cover_path):
            os.remove(cover_path)
    db.session.delete(book)
    db.session.commit()
    flash('Книга удалена', 'success')
    return redirect(url_for('index'))

# --- Вход ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Успешный вход', 'success')
            return redirect(url_for('index'))
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html', form=form)

# --- Выход ---
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists('library.db'):
        with app.app_context():
            db.create_all()
            print('✅ База данных создана')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
