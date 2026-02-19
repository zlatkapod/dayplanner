from datetime import date

def test_save_topic_and_lock(client):
    today = date.today().strftime("%Y-%m-%d")
    # Initial state: not locked
    response = client.get(f"/?date={today}")
    assert b"readonly" not in response.data
    
    # Save topic
    response = client.post("/topic", data={
        "date": today,
        "topic": "My New Topic"
    })
    assert response.status_code == 200
    assert b"My New Topic" in response.data
    assert b"readonly" in response.data
    assert b"locked" in response.data

def test_toggle_topic_lock(client):
    today = date.today().strftime("%Y-%m-%d")
    # First save to lock it
    client.post("/topic", data={"date": today, "topic": "Locked Topic"})
    
    # Toggle to unlock
    response = client.post("/topic/toggle_lock", data={"date": today})
    assert response.status_code == 200
    assert b"readonly" not in response.data
    
    # Toggle to lock
    response = client.post("/topic/toggle_lock", data={"date": today})
    assert response.status_code == 200
    assert b"readonly" in response.data
