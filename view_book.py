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

# --- Добавление книги в подборку ---
@app.route('/add_to_collection/<int:book_id>', methods=['POST'])
@login_required
def add_to_collection(book_id):
    collection_id = request.form.get('collection_id')
    collection = Collection.query.filter_by(id=collection_id, user_id=current_user.id).first()
    if not collection:
        flash('Подборка не найдена.', 'danger')
        return redirect(url_for('view_book', book_id=book_id))
    book = Book.query.get_or_404(book_id)
    if book in collection.books:
        flash('Книга уже в подборке.', 'info')
    else:
        collection.books.append(book)
        db.session.commit()
        flash('Книга добавлена в подборку.', 'success')
    return redirect(url_for('view_book', book_id=book_id))