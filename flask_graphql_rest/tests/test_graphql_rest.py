import graphene
import pytest
from flask import Flask

from flask_graphql_rest import GraphQLREST
from .utils import JSONResponseMixin, ApiClient


@pytest.fixture
def app(schema):
    app = Flask(__name__)

    class TestResponse(app.response_class, JSONResponseMixin):
        pass

    app.response_class = TestResponse
    app.test_client_class = ApiClient

    graphene_rest = GraphQLREST(schema)
    graphene_rest.init_app(app)
    return app


@pytest.yield_fixture
def client(app):
    """A Flask test client. An instance of :class:`flask.testing.TestClient`
    by default.
    """
    with app.test_client() as client:
        yield client


class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="stranger"))

    def resolve_hello(self, info, name):
        return 'Hello ' + name


@pytest.mark.parametrize('schema', [graphene.Schema(query=Query)])
def test_query_hello_world(client):
    response = client.get('/hello?name=foo')
    assert response.status_code == 200
    assert response.json == {
        'data': {'hello': 'Hello foo'}
    }

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


@pytest.mark.parametrize('schema', [graphene.Schema(query=Query, mutation=MyMutations)])
def test_mutation_create_person(client, schema, app):
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
