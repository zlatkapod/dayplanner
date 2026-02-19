from datetime import date

def test_save_topic_no_autolock(client):
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
    assert b"readonly" not in response.data # Should NOT be locked anymore
    assert b"Lock Topic" in response.data # Should show lock button, not unlock

def test_toggle_topic_lock(client):
    today = date.today().strftime("%Y-%m-%d")
    # Initial state: not locked
    response = client.get(f"/?date={today}")
    assert b"readonly" not in response.data

    # Toggle to lock
    response = client.post("/topic/toggle_lock", data={"date": today})
    assert response.status_code == 200
    assert b"readonly" in response.data
    
    # Toggle to unlock
    response = client.post("/topic/toggle_lock", data={"date": today})
    assert response.status_code == 200
    assert b"readonly" not in response.data
