import os
import logging
import time
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
import uuid
import tempfile
from threading import Thread, Event

logging.basicConfig(level=logging.DEBUG)

# Set up the database
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "devkey_change_in_production")

# Configure the SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///whatsapp.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure session to be more secure
app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=5)
app.config["SESSION_FILE_DIR"] = tempfile.gettempdir()

# Configure upload folder
UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# Create a temp dir for direct mode sessions
os.makedirs(os.path.join(UPLOAD_FOLDER, "temp"), exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload size

# Initialize the database with the app
db.init_app(app)

# Import the models (after db initialization to avoid circular imports)
from models import User, Session, MessageCampaign

# Global dictionary to store active messaging threads
active_threads = {}
stop_events = {}

# Import WhatsApp messaging service here (after models to avoid circular imports)
from whatsapp_service import WhatsAppMessenger

@app.route("/")
def index():
    # Direct access to the messaging interface (no login required)
    return render_template("direct_messaging.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists. Please choose a different one.", "danger")
            return redirect(url_for("register"))
        
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("login"))
        
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session.permanent = True
            
            # Create a new session record
            new_session = Session(
                user_id=user.id,
                session_id=str(uuid.uuid4())
            )
            db.session.add(new_session)
            db.session.commit()
            
            session["session_id"] = new_session.session_id
            
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "danger")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    # Clean up any active threads for this user
    if "user_id" in session and session["user_id"] in active_threads:
        if session["user_id"] in stop_events:
            stop_events[session["user_id"]].set()
        
        # Mark the session as inactive in the database
        if "session_id" in session:
            user_session = Session.query.filter_by(session_id=session["session_id"]).first()
            if user_session:
                user_session.is_active = False
                db.session.commit()
    
    # Clear session data
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("Please log in to access the dashboard", "warning")
        return redirect(url_for("login"))
    
    # Get user's campaigns
    user_id = session["user_id"]
    campaigns = MessageCampaign.query.filter_by(user_id=user_id).all()
    
    return render_template("dashboard.html", campaigns=campaigns)

@app.route("/upload_credentials", methods=["POST"])
def upload_credentials():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    if "credentials_file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files["credentials_file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    try:
        # Create user directory if it doesn't exist
        user_dir = os.path.join(app.config["UPLOAD_FOLDER"], str(session["user_id"]))
        os.makedirs(user_dir, exist_ok=True)
        
        # Save the file with a secure filename
        filename = secure_filename(file.filename)
        file_path = os.path.join(user_dir, "credentials.json")
        file.save(file_path)
        
        # Verify if it's a valid JSON
        with open(file_path, "r") as f:
            json.load(f)
        
        return jsonify({"success": True, "message": "Credentials uploaded successfully"})
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Invalid JSON file"}), 400
    except Exception as e:
        app.logger.error(f"Error uploading credentials: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
        
@app.route("/direct_messaging", methods=["POST"])
def direct_messaging():
    """Direct messaging route that doesn't require login"""
    try:
        # Check for required files and data
        if "credentials_file" not in request.files:
            return jsonify({"success": False, "error": "No credentials file provided"}), 400
        
        credentials_file = request.files["credentials_file"]
        if credentials_file.filename == "":
            return jsonify({"success": False, "error": "No credentials file selected"}), 400
        
        # Get form data
        target_number = request.form.get("target_number")
        target_type = request.form.get("target_type", "individual")
        delay_time = request.form.get("delay_time", "5")
        message_text = request.form.get("message_text", "")
        
        if not message_text:
            return jsonify({"success": False, "error": "Message text is required"}), 400
            
        try:
            delay_time = int(delay_time)
        except ValueError:
            return jsonify({"success": False, "error": "Delay time must be a number"}), 400
        
        if not target_number:
            return jsonify({"success": False, "error": "Target number is required"}), 400
        
        # Create a temporary directory with a unique ID for this session
        session_id = str(uuid.uuid4())
        temp_dir = os.path.join(app.config["UPLOAD_FOLDER"], "temp", session_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save the credentials file
        credentials_path = os.path.join(temp_dir, "credentials.json")
        credentials_file.save(credentials_path)
        
        # Verify if it's a valid JSON
        try:
            with open(credentials_path, "r") as f:
                credentials = json.load(f)
        except json.JSONDecodeError:
            return jsonify({"success": False, "error": "Invalid credentials file format"}), 400
            
        # Create a campaign record without user association
        campaign = MessageCampaign(
            user_id=None,  # No user ID since this is direct usage
            target_number=target_number,
            target_type=target_type,
            delay_seconds=delay_time,
            is_active=True
        )
        db.session.add(campaign)
        db.session.commit()
        
        # Create a new stop event
        stop_events[session_id] = Event()
        
        # Inițializăm WhatsAppMessenger pentru trimiterea reală de mesaje
        messenger = WhatsAppMessenger(credentials)
        
        # Pornim thread-ul cu mesageria WhatsApp
        thread = Thread(
            target=messenger.start_messaging,
            args=(target_number, message_text, delay_time, stop_events[session_id], campaign.id)
        )
        thread.daemon = True
        thread.start()
        
        active_threads[session_id] = thread
        
        # Store session ID in browser session for later reference
        session["direct_session_id"] = session_id
        session["direct_campaign_id"] = campaign.id
        
        return jsonify({
            "success": True, 
            "message": "Trimiterea de mesaje WhatsApp a început cu succes",
            "session_id": session_id,
            "campaign_id": campaign.id
        })
        
    except Exception as e:
        app.logger.error(f"Error in direct messaging: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/upload_message", methods=["POST"])
def upload_message():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    if "message_file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files["message_file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    try:
        # Create user directory if it doesn't exist
        user_dir = os.path.join(app.config["UPLOAD_FOLDER"], str(session["user_id"]))
        os.makedirs(user_dir, exist_ok=True)
        
        # Save the file with a secure filename
        filename = secure_filename(file.filename)
        file_path = os.path.join(user_dir, "message.txt")
        file.save(file_path)
        
        # Verify if file is readable
        with open(file_path, "r") as f:
            _ = f.read()
        
        return jsonify({"success": True, "message": "Message file uploaded successfully"})
    except Exception as e:
        app.logger.error(f"Error uploading message file: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/start_messaging", methods=["POST"])
def start_messaging():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    user_id = session["user_id"]
    user_dir = os.path.join(app.config["UPLOAD_FOLDER"], str(user_id))
    
    # Check if files exist
    credentials_file = os.path.join(user_dir, "credentials.json")
    message_file = os.path.join(user_dir, "message.txt")
    
    if not os.path.exists(credentials_file):
        return jsonify({"success": False, "error": "Credentials file not uploaded"}), 400
    
    if not os.path.exists(message_file):
        return jsonify({"success": False, "error": "Message file not uploaded"}), 400
    
    # Get form data
    target_number = request.form.get("target_number")
    target_type = request.form.get("target_type", "individual")
    delay_time = request.form.get("delay_time", "5")
    
    try:
        delay_time = int(delay_time)
    except ValueError:
        return jsonify({"success": False, "error": "Delay time must be a number"}), 400
    
    if not target_number:
        return jsonify({"success": False, "error": "Target number is required"}), 400
    
    # Stop any existing thread for this user
    if user_id in active_threads and active_threads[user_id].is_alive():
        if user_id in stop_events:
            stop_events[user_id].set()
        active_threads[user_id].join(timeout=2)
    
    # Create a new stop event
    stop_events[user_id] = Event()
    
    # Create a new campaign record
    campaign = MessageCampaign(
        user_id=user_id,
        target_number=target_number,
        target_type=target_type,
        delay_seconds=delay_time,
        is_active=True
    )
    db.session.add(campaign)
    db.session.commit()
    
    # Start a new thread for messaging
    try:
        # Load credentials
        with open(credentials_file, "r") as f:
            credentials = json.load(f)
        
        # Load message
        with open(message_file, "r") as f:
            message_text = f.read()
        
        # Initialize WhatsApp messenger
        messenger = WhatsAppMessenger(credentials)
        
        # Start messaging thread
        thread = Thread(
            target=messenger.start_messaging,
            args=(target_number, message_text, delay_time, stop_events[user_id], campaign.id)
        )
        thread.daemon = True
        thread.start()
        
        active_threads[user_id] = thread
        
        return jsonify({
            "success": True, 
            "message": "Messaging started successfully",
            "campaign_id": campaign.id
        })
    except Exception as e:
        app.logger.error(f"Error starting messaging: {str(e)}")
        campaign.is_active = False
        db.session.commit()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/stop_messaging", methods=["POST"])
def stop_messaging():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Not logged in"}), 401
    
    user_id = session["user_id"]
    
    # Set the stop event to stop the thread
    if user_id in stop_events:
        stop_events[user_id].set()
    
    # Update all active campaigns for this user
    campaigns = MessageCampaign.query.filter_by(user_id=user_id, is_active=True).all()
    for campaign in campaigns:
        campaign.is_active = False
    
    db.session.commit()
    
    return jsonify({"success": True, "message": "Messaging stopped successfully"})

@app.route("/stop_direct_messaging", methods=["POST"])
def stop_direct_messaging():
    """Stop direct messaging without requiring login"""
    try:
        # Get session ID from cookie session
        session_id = session.get("direct_session_id")
        campaign_id = session.get("direct_campaign_id")
        
        if not session_id:
            # Try to get from request body
            data = request.get_json()
            if data and "campaign_id" in data:
                campaign_id = data["campaign_id"]
            else:
                return jsonify({"success": False, "error": "No active session found"}), 400
        
        # Set the stop event if it exists
        if session_id in stop_events:
            stop_events[session_id].set()
        
        # Update campaign status in the database if we have the ID
        if campaign_id:
            campaign = MessageCampaign.query.get(campaign_id)
            if campaign:
                campaign.is_active = False
                db.session.commit()
        
        return jsonify({"success": True, "message": "Messaging stopped successfully"})
    
    except Exception as e:
        app.logger.error(f"Error stopping direct messaging: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/campaign_status/<int:campaign_id>")
def campaign_status(campaign_id):
    # Check if we're in direct mode or user authenticated mode
    is_direct_mode = "direct_campaign_id" in session and session["direct_campaign_id"] == campaign_id
    is_authenticated = "user_id" in session
    
    # For direct mode, we don't need user authentication
    if is_direct_mode:
        campaign = MessageCampaign.query.get(campaign_id)
    elif is_authenticated:
        # For authenticated users, check campaign belongs to them
        user_id = session["user_id"]
        campaign = MessageCampaign.query.filter_by(id=campaign_id, user_id=user_id).first()
    else:
        return jsonify({"success": False, "error": "Not authorized to access this campaign"}), 401
    
    if not campaign:
        return jsonify({"success": False, "error": "Campaign not found"}), 404
    
    return jsonify({
        "success": True,
        "is_active": campaign.is_active,
        "messages_sent": campaign.messages_sent,
        "last_update": campaign.updated_at.isoformat() if campaign.updated_at else None
    })

# Initialize the database
with app.app_context():
    db.create_all()
