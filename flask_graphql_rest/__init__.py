from typing import Optional

import flask
import graphene
import graphql.language.ast as graphql_ast
from flask import Response, request
from graphene.test import default_format_error, format_execution_result
from graphql import GraphQLEnumType, GraphQLObjectType, GraphQLScalarType, GraphQLNonNull, GraphQLList
from graphql_server import encode_execution_results, json_encode
from graphene.types.definitions import GrapheneInterfaceType
from graphene.relay import Connection


class GraphQLREST(object):
    schema: graphene.Schema
    app: flask.Flask = None

    def __init__(self, schema: graphene.Schema, app: flask.Flask = None):
        self.schema = schema

        if app is not None:
            self.init_app(app)

    def init_app(self, app: flask.Flask):
        self.app = app

        query_type = self.schema.get_query_type()
        if query_type:
            for field_name, field in query_type.fields.items():
                endpoint = f'query.{query_type.name}.{field_name}'

                app.add_url_rule(f'/{field_name}',
                                 view_func=self._get_query_view_func(field, field_name),
                                 endpoint=endpoint,
                                 methods=['GET'])  # TODO method from meta info

        mutation_type = self.schema.get_mutation_type()
        if mutation_type:
            for field_name, field in mutation_type.fields.items():
                endpoint = f'mutation.{mutation_type.name}.{field_name}'

                app.add_url_rule(f'/{field_name}',
                                 view_func=self._get_mutation_view_func(field, field_name),
                                 endpoint=endpoint,
                                 methods=['POST'])  # TODO method from meta info

    def format_result(self, result):
        return format_execution_result(result, default_format_error)

    def get_return_type(self, return_type):
        if isinstance(return_type, (GraphQLNonNull, GraphQLList)):
            return self.get_return_type(return_type.of_type)

        return return_type

    def _get_field_selection_set(self,
                                 field: graphene.Field,
                                 include_connection: bool = True) -> Optional[graphql_ast.SelectionSet]:



        return_type = self.get_return_type(field.type)

        if isinstance(return_type, (GraphQLScalarType, GraphQLEnumType)):
            return None
        elif isinstance(return_type, (GraphQLObjectType, GrapheneInterfaceType)):
            all_selections = []

            if issubclass(return_type.graphene_type, Connection):
                if include_connection is False:
                    return None
                else:
                    include_connection = False

            for name, sub_field in return_type.fields.items():

                sub_field_type = self.get_return_type(sub_field.type)

                # check if nested connection should be included
                if hasattr(sub_field_type, 'graphene_type') and issubclass(sub_field_type.graphene_type, Connection) and include_connection is False:
                    continue

                selection = graphql_ast.Field(name=graphql_ast.Name(value=name),
                                              selection_set=self._get_field_selection_set(sub_field, include_connection=include_connection))

                all_selections.append(selection)

            return graphql_ast.SelectionSet(
                    selections=all_selections
            )

        raise NotImplementedError

    def _get_query_view_func(self, field: graphene.Field, field_name: str):
        schema = self.schema
        field_selection_set = self._get_field_selection_set(field, include_connection=True)
        variable_definitions = []
        arguments = []

        for arg_name, arg_definition in field.args.items():
            variable = graphql_ast.Variable(name=graphql_ast.Name(value=arg_name))
            arguments.append(graphql_ast.Argument(name=graphql_ast.Name(value=arg_name), value=variable))

            return_type = self.get_return_type(arg_definition.type)

            variable_definitions.append(graphql_ast.VariableDefinition(
                    variable=variable,
                    type=graphql_ast.NamedType(name=graphql_ast.Name(value=return_type.name)),
            ))

        def view_func():
            document_ast = graphql_ast.Document(
                    [
                        graphql_ast.OperationDefinition(
                                operation='query',
                                variable_definitions=variable_definitions,
                                selection_set=graphql_ast.SelectionSet(
                                        selections=[
                                            graphql_ast.Field(
                                                    name=graphql_ast.Name(value=field_name),
                                                    arguments=arguments,
                                                    selection_set=field_selection_set
                                            )
                                        ]
                                )
                        )
                    ]
            )

            variable_values = request.args

            execution_results = schema.execute(
                    document_ast,
                    variable_values=variable_values
            )

            # TODO custom encoder that positions data[field_name] at data
            result, status_code = encode_execution_results([execution_results],
                                                           is_batch=False,
                                                           format_error=default_format_error,
                                                           encode=json_encode)

            return Response(result,
                            status=status_code,
                            content_type='application/json')

        return view_func

    def _get_mutation_view_func(self, field: graphene.Field, field_name: str):
        schema = self.schema
        field_selection_set = self._get_field_selection_set(field, include_connection=True)
        variable_definitions = []
        arguments = []

        for arg_name, arg_definition in field.args.items():
            variable = graphql_ast.Variable(name=graphql_ast.Name(value=arg_name))
            arguments.append(graphql_ast.Argument(name=graphql_ast.Name(value=arg_name), value=variable))
            variable_definitions.append(graphql_ast.VariableDefinition(
                    variable=variable,
                    type=graphql_ast.NamedType(name=graphql_ast.Name(value=arg_definition.type.name)),
                    default_value=arg_definition.default_value
            ))

        def view_func():
            document_ast = graphql_ast.Document(
                    [
                        graphql_ast.OperationDefinition(
                                operation='mutation',
                                variable_definitions=variable_definitions,
                                selection_set=graphql_ast.SelectionSet(
                                        selections=[
                                            graphql_ast.Field(
                                                    name=graphql_ast.Name(value=field_name),
                                                    arguments=arguments,
                                                    selection_set=field_selection_set
                                            )
                                        ]
                                )
                        )
                    ]
            )

            variable_values = request.json

            execution_results = schema.execute(
                    document_ast,
                    variable_values=variable_values
            )

            # TODO custom encoder that positions data[field_name] at data
            result, status_code = encode_execution_results([execution_results],
                                                           is_batch=False,
                                                           format_error=default_format_error,
                                                           encode=json_encode)

            return Response(result,
                            status=status_code,
                            content_type='application/json')

        return view_func
