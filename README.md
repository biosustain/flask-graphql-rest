# Flask-GraphQL-REST
Flask extension to expose a GraphQL API as REST API

### Features
- Generates RESTful endpoints for all query and mutation operations in a GraphQL schema
- Supports GraphQL Relay

### Installation
For installing `flask-graphql-rest`, just run this command in your shell

```bash
pip install "git+https://github.com/biosustain/flask-graphql-rest.git"
```

### Examples
Here are two SQLAlchemy models

```python
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.orm import backref

sa = SQLAlchemy(session_options={"autoflush": False})


class PublisherModel(sa.Model):
    __tablename__ = 'publisher'

    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(sa.DateTime(timezone=True), default=func.now(), nullable=False)
    name = sa.Column(sa.String(length=30))


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
```
To create a GraphQL schema for it you simply have to write the following:

```python
import graphene
from graphene import relay
from graphene_sqlalchemy import SQLAlchemyObjectType, SQLAlchemyConnectionField

class Publisher(SQLAlchemyObjectType):
    class Meta:
        model = PublisherModel
        interfaces = (relay.Node,)


class Book(SQLAlchemyObjectType):
    class Meta:
        model = BookModel
        interfaces = (relay.Node,)


class Query(graphene.ObjectType):
    node = relay.Node.Field()
    books = SQLAlchemyConnectionField(Book)


schema = graphene.Schema(query=Query)
```
Then you can simply use `flask-graphql-rest` to create RESTful API from GraphQL schema:
```python
from flask import Flask
from flask_graphql_rest import GraphQLREST


app = Flask(__name__)
graphene_rest = GraphQLREST(schema)
graphene_rest.init_app(app)
```

Now we can use [HTTPie](https://github.com/jakubroztocil/httpie) to test these newly created end points:
#### Fetch list of `Book` objects
```bash
http ":8005/books"
```
```json
{
    "data": {
        "books": {
            "edges": [
                {
                    "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                    "node": {
                        "id": "Qm9vazox",
                        "publisher": {
                            "id": "UHVibGlzaGVyOjE="
                        },
                        "publisherId": 1,
                        "title": "Python Microservices Development"
                    }
                },
                {
                    "cursor": "YXJyYXljb25uZWN0aW9uOjE=",
                    "node": {
                        "id": "Qm9vazoy",
                        "publisher": {
                            "id": "UHVibGlzaGVyOjI="
                        },
                        "publisherId": 2,
                        "title": "Functional Programming in Python"
                    }
                }
            ],
            "pageInfo": {
                "endCursor": "YXJyYXljb25uZWN0aW9uOjE=",
                "hasNextPage": false,
                "hasPreviousPage": false,
                "startCursor": "YXJyYXljb25uZWN0aW9uOjA="
            }
        }
    }
}
```
#### Fetch a `Book` object by node id
```bash
http ":8005/node?id=Qm9vazox"
```
```json
{
    "data": {
        "node": {
            "id": "Qm9vazox",
            "publisher": {
                "id": "UHVibGlzaGVyOjE="
            },
            "publisherId": 1,
            "title": "Python Microservices Development"
        }
    }
}
```

#### Fetch a `Publisher` object by node id
```bash
http ":8005/node?id=UHVibGlzaGVyOjE="
```
```json
{
    "data": {
        "node": {
            "books": {
                "edges": [
                    {
                        "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                        "node": {
                            "id": "Qm9vazox"
                        }
                    }
                ],
                "pageInfo": {
                    "endCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                    "hasNextPage": false,
                    "hasPreviousPage": false,
                    "startCursor": "YXJyYXljb25uZWN0aW9uOjA="
                }
            },
            "createdAt": "2017-10-12T07:42:15",
            "id": "UHVibGlzaGVyOjE=",
            "name": "Packt"
        }
    }
}

```


To learn more check out the following [examples](examples/):

* **Full example**: [Flask SQLAlchemy example](examples/example_app.py)
