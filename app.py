from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL
import os
import joblib
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize Flask app
app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'UTKARSHANi@1511'
app.config['MYSQL_DB'] = 'pcos_detection'
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'

# Initialize MySQL
mysql = MySQL(app)

# Load ML model
model_filename = "random_forest_pcos_18_features.pkl"
model_path = os.path.join(os.getcwd(), model_filename)

if not os.path.exists(model_path):
    raise FileNotFoundError(f"Model file not found: {model_path}")

try:
    model = joblib.load(model_path)
except Exception as e:
    raise RuntimeError(f"Error loading model: {e}")

# Routes
@app.route('/')
def home():
    return redirect(url_for('pcos123')) if 'user_id' in session else redirect(url_for('login'))

@app.route('/pcos123')
def pcos123():
    if 'user_id' not in session:
        flash('Please log in first', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE id = %s", (session['user_id'],))
    username = cur.fetchone()[0]
    cur.close()
    return render_template("pcos123.html", username=username)

@app.route('/dietplan')
def dietplan():
    return render_template("dietplan.html")

@app.route('/exercise_plan')
def exercise_plan():
    return render_template("exercise_plan.html")

@app.route('/detect')
def detect():
    if 'user_id' not in session:
        flash('Please log in first', 'danger')
        return redirect(url_for('login'))
    return render_template("detect.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session.permanent = True
            flash('Login successful!', 'success')
            return redirect(url_for('pcos123'))

        flash('Invalid email or password. Try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not all([username, email, password]):
            flash('All fields are required', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            flash('Email already registered. Please log in.', 'warning')
            cur.close()
            return redirect(url_for('login'))

        try:
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, hashed_password))
            mysql.connection.commit()

            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            new_user = cur.fetchone()
            session['user_id'] = new_user[0]
            session.permanent = True
            flash('Registration successful! Redirecting...', 'success')
        except Exception as e:
            flash(f"Error during registration: {e}", 'danger')
        finally:
            cur.close()
            return redirect(url_for('pcos123'))

    return render_template('register.html')

@app.route('/predict', methods=['POST'])
def predict():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized access. Please log in.'}), 403

    try:
        data = request.get_json()
        required_fields = [
            'age', 'bmi', 'cycleLength', 'cycleValue', 'amh', 'fshlh', 'fsh', 'weightGain',
            'follicleNoL', 'follicleNoR', 'avgFollicleSize', 'weight', 'height',
            'waistHipRatio', 'hairGrowth', 'pimples', 'hairLoss'
        ]

        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing input data'}), 400

        features = np.array([[data[field] for field in required_fields]])
        prediction = model.predict(features)
        result = "Possibility of PCOS" if prediction[0] == 1 else "No PCOS"

        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO predictions (user_id, age, bmi, cycle_length, cycle_value, amh, fshlh, fsh,
                weight_gain, follicle_no_l, follicle_no_r, avg_follicle_size, weight, height,
                waist_hip_ratio, hair_growth, pimples, hair_loss, result)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (session['user_id'], *features[0], result))
            mysql.connection.commit()
            cur.close()
        except Exception as db_err:
            print(f"Skipping DB save (table may not exist): {db_err}")

        return jsonify({'message': result})

    except Exception as e:
        print(f"Prediction error: {e}")
        return jsonify({'error': str(e)}), 400

if __name__ == "__main__":
    app.run(debug=True)