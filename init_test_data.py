from models import db, User, Role, Book, Genre
from werkzeug.security import generate_password_hash
from app import app

with app.app_context():
    db.create_all()

    admin_role = Role(name='Администратор', description='Полный доступ')
    moder_role = Role(name='Модератор', description='Редактирование книг и рецензий')
    user_role = Role(name='Пользователь', description='Может оставлять рецензии')

    db.session.add_all([admin_role, moder_role, user_role])
    db.session.commit()

    users = [
        User(username='admin', password_hash=generate_password_hash('adminpass'),
             last_name='Админов', first_name='Админ', middle_name='Админович', role=admin_role),
        User(username='mod', password_hash=generate_password_hash('modpass'),
             last_name='Модеров', first_name='Мод', middle_name='Модович', role=moder_role),
        User(username='user', password_hash=generate_password_hash('userpass'),
             last_name='Юзеров', first_name='Юзер', middle_name='Юзерович', role=user_role)
    ]
    db.session.add_all(users)

    genres = [Genre(name=name) for name in ['Фантастика', 'Приключения', 'Научные']]
    db.session.add_all(genres)
    db.session.commit()

    books = [
        Book(title='Звёздный путь', description='Про космос и приключения.', year=2020,
             publisher='КосмоИздат', author='Иван Космонавтов', pages=320,
             genres=[genres[0], genres[1]]),
        Book(title='Мозг и разум', description='Научные исследования о мозге.', year=2021,
             publisher='НаукаПресс', author='Доктор Разумов', pages=280,
             genres=[genres[2]])
    ]

    db.session.add_all(books)
    db.session.commit()
    print('✅ Пользователи, роли, жанры и книги успешно добавлены.')
