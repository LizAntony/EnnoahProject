# app.py
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
import pyodbc

load_dotenv()

ACCESS_DB_PATH = os.getenv("ACCESS_DB_PATH", "C:/Liz/Clark/All_Documents/MBASecondSemester/SchoolSubjects/LizProjectRequirement/Project/data/meetings.accdb")
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
SECRET_KEY = os.getenv("SECRET_KEY", "dev")

app = Flask(__name__)
app.secret_key = SECRET_KEY

def get_conn():
    return pyodbc.connect(
        fr"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={ACCESS_DB_PATH};"
    )

def create_meeting(title, organizer_email, attendee_email, start_time, end_time, external_link, notes):
    join_token = uuid.uuid4().hex[:16]  # short unique token
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO Meetings (Title, OrganizerEmail, AttendeeEmail, StartTime, EndTime, JoinToken, ExternalLink, Notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, organizer_email, attendee_email, start_time, end_time, join_token, external_link, notes))
    conn.commit()
    cur.close()
    conn.close()
    return join_token

def get_meetings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT ID, Title, OrganizerEmail, AttendeeEmail, StartTime, EndTime, JoinToken, ExternalLink FROM Meetings ORDER BY StartTime DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def get_meeting_by_token(token):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT ID, Title, OrganizerEmail, AttendeeEmail, StartTime, EndTime, JoinToken, ExternalLink, Notes FROM Meetings WHERE JoinToken = ?", (token,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

@app.route("/")
def index():
    meetings = get_meetings()
    return render_template("index.html", meetings=meetings, base_url=BASE_URL)

@app.route("/schedule", methods=["GET", "POST"])
def schedule():
    if request.method == "POST":
        title = request.form.get("title") or "Meeting"
        organizer_email = request.form.get("organizer_email") or ""
        attendee_email = request.form.get("attendee_email") or ""
        start_time_str = request.form.get("start_time")
        end_time_str = request.form.get("end_time")
        external_link = request.form.get("external_link") or ""
        notes = request.form.get("notes") or ""

        try:
            # Expect ISO format like 2025-11-29T17:30
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.fromisoformat(end_time_str)
            if end_time <= start_time:
                flash("End time must be after start time.", "error")
                return redirect(url_for("schedule"))
        except Exception:
            flash("Invalid date/time format. Use the picker.", "error")
            return redirect(url_for("schedule"))

        token = create_meeting(title, organizer_email, attendee_email, start_time, end_time, external_link, notes)
        join_url = f"{BASE_URL}/join/{token}"
        flash(f"Meeting scheduled. Share this link: {join_url}", "success")
        return redirect(url_for("index"))
    return render_template("schedule.html")

@app.route("/join/<token>")
def join(token):
    mtg = get_meeting_by_token(token)
    if not mtg:
        return render_template("join.html", error="Invalid or expired link.", meeting=None)

    # mtg columns: 0:ID,1:Title,2:OrgEmail,3:AttEmail,4:Start,5:End,6:Token,7:ExternalLink,8:Notes
    meeting = {
        "id": mtg[0],
        "title": mtg[1],
        "organizer_email": mtg[2],
        "attendee_email": mtg[3],
        "start_time": mtg[4],
        "end_time": mtg[5],
        "token": mtg[6],
        "external_link": mtg[7] or "",
        "notes": mtg[8] or ""
    }
    return render_template("join.html", meeting=meeting)
    
def build_ics(meeting, base_url):
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//MeetingScheduler//EN
BEGIN:VEVENT
UID:{meeting['token']}@meetings
DTSTAMP:{meeting['start_time'].strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{meeting['start_time'].strftime('%Y%m%dT%H%M%SZ')}
DTEND:{meeting['end_time'].strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{meeting['title']}
DESCRIPTION:Join link: {base_url}/join/{meeting['token']}
END:VEVENT
END:VCALENDAR
"""
    return ics

if __name__ == "__main__":
    app.run(debug=True)