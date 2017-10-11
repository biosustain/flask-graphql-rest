import graphene
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from sqlalchemy import func
from sqlalchemy.orm import backref

from flask_graphql_rest import GraphQLREST

sa = SQLAlchemy(session_options={"autoflush": False})


# Define your models
class PublisherModel(sa.Model):
    __tablename__ = 'publisher'

    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=func.now(), nullable=False)
    name = sa.Column(sa.String(length=30))


class AuthorModel(sa.Model):
    __tablename__ = 'author'

    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=func.now(), nullable=False)
    name = sa.Column(sa.String(length=30))


class AuthorBookAssociationModel(sa.Model):
    __tablename__ = 'author_book_association'
    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=func.now(), nullable=False)
    author_id = sa.Column(sa.Integer, sa.ForeignKey('author.id'))
    book_id = sa.Column(sa.Integer, sa.ForeignKey('book.id'))


class BookModel(sa.Model):
    __tablename__ = 'book'
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.String(length=30))
    publisher_id = sa.Column(sa.Integer,
                             sa.ForeignKey('publisher.id'),
                             nullable=True)

    # orm relationships
    publisher = sa.relationship(PublisherModel,
                                backref=backref('books', uselist=True),
                                uselist=False)
    authors = sa.relationship(AuthorModel,
                              backref=backref('books', uselist=True),
                              secondary=AuthorBookAssociationModel.__table__)


# Define your Graphene objects
class Publisher(SQLAlchemyObjectType):
    class Meta:
        model = PublisherModel
        interfaces = (relay.Node,)


class Author(SQLAlchemyObjectType):
    class Meta:
        model = AuthorModel
        interfaces = (relay.Node,)


class Book(SQLAlchemyObjectType):
    class Meta:
        model = BookModel
        interfaces = (relay.Node,)


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    books = SQLAlchemyConnectionField(Book)
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    def resolve_hello(self, info, name):
        return 'Hello ' + name


class Person(graphene.ObjectType):
    name = graphene.String()
    age = graphene.Int()


class CreatePerson(graphene.Mutation):
    class Arguments:
        name = graphene.String()
        age = graphene.Int()

    ok = graphene.Boolean()
    person = graphene.Field(lambda: Person)

    def mutate(self, info, name, age):
        person = Person(name=name, age=age)
        ok = True
        return CreatePerson(person=person, ok=ok)


class MyMutations(graphene.ObjectType):
    create_person = CreatePerson.Field()


# Create Graphene Schema
schema = graphene.Schema(
    query=Query,
    mutation=MyMutations
)


def create_app():
    app = Flask(__name__)


    with app.app_context():
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
        sa.init_app(app)

        sa.create_all()
        initialize_data()

        graphene_rest = GraphQLREST(schema)
        graphene_rest.init_app(app)

    return app


def initialize_data():
    publisher_1 = PublisherModel(name='Packt')
    publisher_2 = PublisherModel(name='O\'Reilly Media')
    sa.session.add(publisher_1)
    sa.session.add(publisher_2)

    author_1 = AuthorModel(name='Tarek Ziade')
    author_2 = AuthorModel(name='David Mertz')
    sa.session.add(author_1)
    sa.session.add(author_2)

    sa.session.flush()

    book_1 = BookModel(title='Python Microservices Development', publisher=publisher_1)
    book_1.authors.append(author_1)
    book_2 = BookModel(title='Functional Programming in Python', publisher=publisher_2)
    book_2.authors.append(author_2)

    sa.session.add(book_1)
    sa.session.add(book_2)

    sa.session.commit()


if __name__ == '__main__':
    app = create_app()

    app.run(port=8005, debug=True)
