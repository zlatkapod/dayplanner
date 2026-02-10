import json

def test_topics_page(client):
    response = client.get("/topics")
    assert response.status_code == 200
    assert b"Topics" in response.data

def test_add_topic(client):
    response = client.post("/topics/add", data={
        "text": "New Interesting Topic",
        "category": "Tech"
    })
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/topics"
    
    # Verify via load_topics since HTMX redirect doesn't automatically follow in client.post
    import app as app_module
    data = app_module.load_topics()
    assert any(t["text"] == "New Interesting Topic" for t in data["topics"])

def test_delete_topic(client):
    # First add a topic to get its ID
    client.post("/topics/add", data={
        "text": "To be deleted",
        "category": "Misc"
    })
    import app as app_module
    data = app_module.load_topics()
    tid = next(t["id"] for t in data["topics"] if t["text"] == "To be deleted")
    
    response = client.post("/topics/delete", data={"id": tid})
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/topics"
    
    data = app_module.load_topics()
    assert not any(t["text"] == "To be deleted" for t in data["topics"])

def test_qna_page(client):
    response = client.get("/qna")
    assert response.status_code == 200
    assert b"Q&A Inbox" in response.data

def test_add_qna_question(client):
    response = client.post("/qna/question/add", data={
        "text": "What is life?"
    })
    assert response.status_code == 200
    assert b"What is life?" in response.data

def test_tools_page(client):
    response = client.get("/tools")
    assert response.status_code == 200
    assert b"Tools" in response.data

def test_add_tool_category(client):
    response = client.post("/tools/category/add", data={
        "name": "Testing Tools"
    })
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/tools"
    
    response = client.get("/tools")
    assert b"Testing Tools" in response.data

def test_subscriptions_page(client):
    response = client.get("/subscriptions")
    assert response.status_code == 200
    assert b"Subscriptions" in response.data
