import json
import datetime
from datetime import date

def test_dashboard_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data

def test_dayplanner_page(client):
    response = client.get("/dayplanner")
    assert response.status_code == 200
    assert b"Day Planner" in response.data

def test_add_todo(client):
    today = date.today().strftime("%Y-%m-%d")
    response = client.post("/todo", data={
        "date": today,
        "text": "Test Todo",
        "minutes": "20"
    })
    assert response.status_code == 200
    assert b"Test Todo 20min" in response.data

def test_todo_sorting(client):
    today = date.today().strftime("%Y-%m-%d")
    # Add a done todo
    client.post("/todo", data={"date": today, "text": "Done Todo"})
    client.post("/todo/done", data={"date": today, "index": "0"})
    
    # Add a new todo
    client.post("/todo", data={"date": today, "text": "New Undone Todo"})
    
    response = client.get("/dayplanner")
    # The new undone todo should be before the done todo
    content = response.data.decode()
    assert content.find("New Undone Todo") < content.find("Done Todo")

def test_delete_todo(client):
    today = date.today().strftime("%Y-%m-%d")
    client.post("/todo", data={"date": today, "text": "To Delete"})
    response = client.post("/todo/delete", data={"date": today, "index": "0"})
    assert b"To Delete" not in response.data

def test_move_todo_next_day(client):
    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    tomorrow_str = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    client.post("/todo", data={"date": today_str, "text": "Move Me"})
    response = client.post("/todo/move_next", data={"date": today_str, "index": "0"})
    
    assert b"Move Me" not in response.data
    
    # Check tomorrow's page
    response_tomorrow = client.get(f"/dayplanner?date={tomorrow_str}")
    assert b"Move Me" in response_tomorrow.data

def test_update_settings(client):
    today = date.today().strftime("%Y-%m-%d")
    response = client.post("/settings", data={
        "date": today,
        "start": "10:00",
        "end": "18:00"
    })
    assert response.status_code == 200
    assert b"10:00" in response.data
    assert b"17:40" in response.data # Last block starts at 17:40
    assert b"18:00" not in response.data # Grid shows start times

def test_set_block(client):
    today = date.today().strftime("%Y-%m-%d")
    response = client.post("/block", data={
        "date": today,
        "time": "09:00",
        "text": "Coding"
    })
    assert response.status_code == 200
    assert b"Coding" in response.data

def test_save_note(client):
    today = date.today().strftime("%Y-%m-%d")
    response = client.post("/note", data={
        "date": today,
        "text": "Daily reflection"
    })
    assert response.status_code == 204
    
    response = client.get(f"/?date={today}")
    assert b"Daily reflection" in response.data
