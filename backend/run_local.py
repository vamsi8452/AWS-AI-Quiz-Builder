from app import handler


def print_response(label, response):
    print(f"\n{label}")
    print(response)


create_event = {
    "version": "2.0",
    "rawPath": "/study-sets",
    "requestContext": {"http": {"method": "POST"}},
    "body": "{\"text\":\"AWS VPC basics. Subnets, route tables, gateways.\"}",
    "isBase64Encoded": False,
}

create_response = handler(create_event, None)
print_response("CREATE", create_response)

create_body = create_response.get("body", "{}")
study_id = __import__("json").loads(create_body).get("id")

list_event = {
    "version": "2.0",
    "rawPath": "/study-sets",
    "requestContext": {"http": {"method": "GET"}},
}
print_response("LIST", handler(list_event, None))

if study_id:
    quiz_event = {
        "version": "2.0",
        "rawPath": f"/study-sets/{study_id}/quiz",
        "requestContext": {"http": {"method": "POST"}},
    }
    quiz_response = handler(quiz_event, None)
    print_response("QUIZ", quiz_response)

    quiz_body = quiz_response.get("body", "{}")
    quiz = __import__("json").loads(quiz_body).get("quiz", [])
    answers = [0 for _ in quiz]
    validate_event = {
        "version": "2.0",
        "rawPath": f"/study-sets/{study_id}/validate",
        "requestContext": {"http": {"method": "POST"}},
        "body": __import__("json").dumps({"answers": answers}),
        "isBase64Encoded": False,
    }
    print_response("VALIDATE", handler(validate_event, None))
