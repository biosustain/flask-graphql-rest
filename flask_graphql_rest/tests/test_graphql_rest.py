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


def test_query_node(client, models, sa):
    publisher = models.Publisher(name='Packt')
    sa.session.add(publisher)

    author = models.Author(name='Tarek Ziade')
    sa.session.add(author)
    sa.session.commit()

    book = models.Book(title='Python Microservices Development', publisher=publisher)
    book.authors.append(author)
    sa.session.add(book)

    sa.session.commit()

    publisher_node_id = relay.Node.to_global_id('Publisher', publisher.id)
    author_node_id = relay.Node.to_global_id('Author', author.id)
    book_node_id = relay.Node.to_global_id('Book', book.id)

    # Test for Publisher node
    response = client.get(f'/node?id={publisher_node_id}')
    assert response.status_code == 200
    assert response.json['data']['node']['id'] == publisher_node_id
    assert response.json['data']['node']['name'] == publisher.name
    assert len(response.json['data']['node']['books']['edges']) == 1

    # nested nodes in `to_many` relationship should return only `id` field
    assert response.json['data']['node']['books']['edges'][0]['node'] == {'id': book_node_id}

    # Test for Author node
    response = client.get(f'/node?id={author_node_id}')
    assert response.status_code == 200
    assert response.json['data']['node']['id'] == author_node_id
    assert response.json['data']['node']['name'] == author.name
    assert len(response.json['data']['node']['books']['edges']) == 1

    # nested nodes in `to_many` relationship should return only `id` field
    assert response.json['data']['node']['books']['edges'][0]['node'] == {'id': book_node_id}

    # Test for Book node
    response = client.get(f'/node?id={book_node_id}')
    assert response.status_code == 200
    assert response.json['data']['node']['id'] == book_node_id
    assert response.json['data']['node']['title'] == book.title

    # nested node in `to_one` relationship should return only `id` field
    assert response.json['data']['node']['publisher'] == {'id': publisher_node_id}

    assert len(response.json['data']['node']['authors']['edges']) == 1

    # nested nodes in `to_many` relationship should return only `id` field
    assert response.json['data']['node']['authors']['edges'][0]['node'] == {'id': author_node_id}


def test_query_connection(client, models, sa):
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

    # status code should be `OK`
    assert response.status_code == 200
    assert len(response.json['data']['books']['edges']) == 2
    assert response.json['data']['books']['pageInfo']['hasNextPage'] is False
    assert response.json['data']['books']['pageInfo']['hasPreviousPage'] is False
    assert response.json['data']['books']['edges'][0]['node']['title'] == book_1.title
    assert response.json['data']['books']['edges'][1]['node']['title'] == book_2.title

    # nested node in `to_one` relationship should return only `id` field
    assert response.json['data']['books']['edges'][0]['node']['publisher'] == {
        'id': relay.Node.to_global_id('Publisher', publisher_1.id)}
    assert response.json['data']['books']['edges'][1]['node']['publisher'] == {
        'id': relay.Node.to_global_id('Publisher', publisher_2.id)}

    # nested nodes in `to_many` relationship should return only `id` field
    assert len(response.json['data']['books']['edges'][0]['node']['authors']['edges']) == 1
    assert response.json['data']['books']['edges'][0]['node']['authors']['edges'][0]['node'] == {
        'id': relay.Node.to_global_id('Author', author_1.id)}
    assert len(response.json['data']['books']['edges'][1]['node']['authors']['edges']) == 1
    assert response.json['data']['books']['edges'][1]['node']['authors']['edges'][0]['node'] == {
        'id': relay.Node.to_global_id('Author', author_2.id)}

    # Test pagination filters, limit by first
    response = client.get('/books?first=1')
    assert response.status_code == 200
    assert len(response.json['data']['books']['edges']) == 1
    assert response.json['data']['books']['pageInfo']['hasNextPage'] is True
    assert response.json['data']['books']['pageInfo']['hasPreviousPage'] is False
    assert response.json['data']['books']['edges'][0]['node']['title'] == book_1.title

    # Test pagination filters, limit by last
    response = client.get('/books?last=1')
    assert response.status_code == 200
    assert len(response.json['data']['books']['edges']) == 1
    assert response.json['data']['books']['pageInfo']['hasNextPage'] is False
    assert response.json['data']['books']['pageInfo']['hasPreviousPage'] is True
    assert response.json['data']['books']['edges'][0]['node']['title'] == book_2.title
