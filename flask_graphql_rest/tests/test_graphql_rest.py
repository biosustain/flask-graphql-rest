import graphene
import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField
from sqlalchemy import func
from sqlalchemy.orm import backref

from flask_graphql_rest import GraphQLREST
from .utils import JSONResponseMixin, ApiClient


@pytest.fixture
def app():
    app = Flask(__name__)

    class TestResponse(app.response_class, JSONResponseMixin):
        pass

    app.response_class = TestResponse
    app.test_client_class = ApiClient
    return app


@pytest.yield_fixture
def client(app, schema):
    """A Flask test client. An instance of :class:`flask.testing.TestClient`
    by default.
    """
    with app.test_client() as client:
        yield client


@pytest.yield_fixture
def sa(app):
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

    sa = SQLAlchemy(app)

    return sa


@pytest.yield_fixture
def models(sa):
    class Publisher(sa.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        created_at = sa.Column(sa.DateTime(timezone=True), default=func.now(), nullable=False)
        name = sa.Column(sa.String(length=30))

    class Author(sa.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        created_at = sa.Column(sa.DateTime(timezone=True), default=func.now(), nullable=False)
        name = sa.Column(sa.String(length=30))

    class AuthorBookAssociation(sa.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        created_at = sa.Column(sa.DateTime(timezone=True), default=func.now(), nullable=False)
        author_id = sa.Column(sa.Integer, sa.ForeignKey('author.id'))
        book_id = sa.Column(sa.Integer, sa.ForeignKey('book.id'))

    class Book(sa.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        title = sa.Column(sa.String(length=30))
        publisher_id = sa.Column(sa.Integer,
                                 sa.ForeignKey('publisher.id'),
                                 nullable=True)

        # orm relationships
        publisher = sa.relationship(Publisher,
                                    backref=backref('books', uselist=True),
                                    uselist=False)
        authors = sa.relationship(Author,
                                  backref=backref('books', uselist=True),
                                  secondary=AuthorBookAssociation.__table__)

    class Object(object):
        pass

    _models = Object()
    _models.Publisher = Publisher
    _models.Author = Author
    _models.Book = Book
    _models.sa = sa

    sa.create_all()

    return _models


@pytest.yield_fixture
def schema(models, app):
    class Publisher(SQLAlchemyObjectType):
        class Meta:
            model = models.Publisher
            interfaces = (relay.Node,)

    class Author(SQLAlchemyObjectType):
        class Meta:
            model = models.Author
            interfaces = (relay.Node,)

    class Book(SQLAlchemyObjectType):
        class Meta:
            model = models.Book
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

    _schema = graphene.Schema(
        query=Query,
        mutation=MyMutations
    )
    graphene_rest = GraphQLREST(_schema)
    graphene_rest.init_app(app)

    return _schema


def test_query_hello_world(client):
    response = client.get('/hello?name=foo')
    assert response.status_code == 200
    assert response.json == {
        'data': {'hello': 'Hello foo'}
    }


def test_mutation_create_person(client):
    response = client.post('/createPerson', data={'name': 'foo', 'age': 20})
    assert response.status_code == 200
    assert response.json == {
        'data': {
            'createPerson': {
                'person': {
                    'name': 'foo',
                    'age': 20
                },
                'ok': True
            }
        }
    }


# TODO test with relay.Node fields (stand-alone, in list, nested)

# class IntroduceShip(relay.ClientIDMutation):
#
#     class Input:
#         ship_name = graphene.String(required=True)
#         faction_id = graphene.String(required=True)
#
#     ship = graphene.Field(Ship)
#     faction = graphene.Field(Faction)
#
#     @classmethod
#     def mutate_and_get_payload(cls, root, info, **input):
#         ship_name = input.ship_name
#         faction_id = input.faction_id
#         ship = create_ship(ship_name, faction_id)
#         faction = get_faction(faction_id)
#         return IntroduceShip(ship=ship, faction=faction)
#


def test_query_stand_alone_node(client, models, sa):
    publisher_1 = models.Publisher(name='Packt')
    publisher_2 = models.Publisher(name='O\'Reilly Media')
    sa.session.add(publisher_1)
    sa.session.add(publisher_2)
    sa.session.commit()

    author_1 = models.Author(name='Tarek Ziade')
    sa.session.add(author_1)
    author_2 = models.Author(name='David Mertz')
    sa.session.commit()

    book_1 = models.Book(title='Python Microservices Development', publisher=publisher_1)
    book_1.authors.append(author_1)
    sa.session.add(book_1)
    book_2 = models.Book(title='Functional Programming in Python', publisher=publisher_2)
    book_2.authors.append(author_2)
    sa.session.add(book_2)
    sa.session.commit()

    response = client.get('/books')

    assert response.status_code == 200
    assert len(response.json['data']['books']['edges']) == 2
