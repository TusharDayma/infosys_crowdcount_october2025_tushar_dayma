from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from dotenv import load_dotenv
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-prod'  # Change this!

# Load environment variables
load_dotenv()
mongo_uri = os.getenv('MONGODB_URI')

# MongoDB Atlas connection
client = MongoClient(mongo_uri)
db = client['login_app']  # Database name
users_collection = db['users']  # Collection name

# # One-time script to add admin user (run once, then comment out)
# users_collection.insert_one({
#     'username': 'admin',
#     'password': generate_password_hash('adminpass'),
#     'role': 'admin'
# })

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = users_collection.find_one({'username': username})
        
        if user and check_password_hash(user['password'], password):
            session['username'] = username
            session['role'] = user['role']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials!', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if users_collection.find_one({'username': username}):
            flash('Username already exists!', 'error')
        else:
            hashed_password = generate_password_hash(password)
            users_collection.insert_one({
                'username': username,
                'password': hashed_password,
                'role': 'user'  # Default role; admins set manually in DB
            })
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    role = session.get('role', 'user')
    username = session['username']
    
    if role == 'admin':
        content = "Welcome, Admin! You can manage users and settings here."
    else:
        content = f"Welcome, {username}! You can view your profile here."
    
    return render_template('dashboard.html', role=role, content=content, username=username)

@app.route('/crowd_control')
def crowd_control():
    if 'username' not in session:
        return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash('Access denied: Admins only!', 'error')
        return redirect(url_for('dashboard'))
    return render_template('crowd_control.html')

@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('history.html')

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html', username=session['username'])

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)