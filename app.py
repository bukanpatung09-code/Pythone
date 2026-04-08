from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_NAME = 'merchant_data.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS merchants 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             nama TEXT, toko TEXT, no_hp TEXT UNIQUE, email TEXT UNIQUE, 
             password TEXT, saldo INTEGER DEFAULT 0, foto TEXT)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS topup_requests 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             email TEXT, toko TEXT, jumlah INTEGER, status TEXT DEFAULT 'pending')''')
        # Tabel notifikasi baru
        conn.execute('''CREATE TABLE IF NOT EXISTS notifications 
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL,
              type TEXT NOT NULL,
              title TEXT NOT NULL,
              message TEXT NOT NULL,
              related_id INTEGER,
              is_read INTEGER DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY (email) REFERENCES merchants(email))''')
        conn.commit()

def create_notification(email, notification_type, title, message, related_id=None):
    """Fungsi helper untuk membuat notifikasi"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("""INSERT INTO notifications (email, type, title, message, related_id) 
                           VALUES (?, ?, ?, ?, ?)""",
                         (email, notification_type, title, message, related_id))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("INSERT INTO merchants (nama, toko, no_hp, email, password, saldo) VALUES (?, ?, ?, ?, ?, ?)",
                         (data['nama'], data['nama'], data['no_hp'], data['email'], data['pass'], 0))
            conn.commit()
        
        # Buat notifikasi selamat datang
        create_notification(
            data['email'],
            'welcome',
            'Selamat Datang!',
            f"Akun {data['nama']} telah berhasil dibuat. Mulai gunakan aplikasi sekarang!"
        )
        
        return jsonify({"status": "success", "message": "Registrasi Berhasil! Silakan Login."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"status": "error", "message": "Email/No HP sudah terdaftar!"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM merchants WHERE (email = ? OR no_hp = ?) AND password = ?"
            user = conn.execute(query, (data['identifier'], data['identifier'], data['pass'])).fetchone()
        
        if user:
            u = dict(user)
            display_toko = u.get('toko') or u.get('nama') or "Merchant"
            return jsonify({
                "status": "success",
                "message": f"Selamat Datang, {display_toko}!",
                "user": {
                    "nama": u.get('nama') or "-",
                    "toko": display_toko,
                    "saldo": u.get('saldo') or 0,
                    "no_hp": u.get('no_hp'),
                    "email": u.get('email'),
                    "foto": u.get('foto')
                }
            }), 200
        return jsonify({"status": "error", "message": "Email atau Password salah!"}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get_profile', methods=['GET'])
def get_profile():
    email = request.args.get('email')
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            user = conn.execute("SELECT * FROM merchants WHERE email = ?", (email,)).fetchone()
        
        if user:
            u = dict(user)
            print("Sinkron Berhasil!")
            return jsonify({
                "status": "success",
                "user": {
                    "toko": u.get('toko') or u.get('nama'),
                    "no_hp": u.get('no_hp'),
                    "email": u.get('email'),
                    "saldo": u.get('saldo'),
                    "foto": u.get('foto')
                }
            }), 200
        return jsonify({"status": "error", "message": "User tidak ditemukan"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/request_topup', methods=['POST'])
def request_topup():
    data = request.json
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.execute("INSERT INTO topup_requests (email, toko, jumlah) VALUES (?, ?, ?)",
                         (data['email'], data['toko'], data['jumlah']))
            conn.commit()
            request_id = cursor.lastrowid
        
        # Buat notifikasi untuk user
        create_notification(
            data['email'],
            'topup_request',
            'Permintaan Top Up Dikirim',
            f"Permintaan top up sebesar Rp {data['jumlah']:,} telah dikirim. Tunggu persetujuan admin.",
            request_id
        )
        
        return jsonify({"status": "success", "message": "Permintaan terkirim!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/admin/requests', methods=['GET'])
def get_admin_requests():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        reqs = conn.execute("SELECT * FROM topup_requests WHERE status = 'pending'").fetchall()
    return jsonify([dict(r) for r in reqs])

@app.route('/admin/approve', methods=['POST'])
def approve_topup():
    data = request.json
    try:
        with sqlite3.connect(DB_NAME) as conn:
            # Dapatkan data topup request
            conn.row_factory = sqlite3.Row
            topup = conn.execute("SELECT * FROM topup_requests WHERE id = ?", 
                                (data['id_request'],)).fetchone()
            
            if not topup:
                return jsonify({"status": "error", "message": "Request tidak ditemukan"}), 404
            
            topup_dict = dict(topup)
            
            # Update Saldo (Matematika)
            conn.execute("UPDATE merchants SET saldo = saldo + ? WHERE email = ?", 
                         (int(data['jumlah']), data['email']))
            # Update Status
            conn.execute("UPDATE topup_requests SET status = 'success' WHERE id = ?", 
                         (data['id_request'],))
            conn.commit()
        
        # Buat notifikasi untuk user bahwa top up disetujui
        create_notification(
            data['email'],
            'topup_approved',
            'Top Up Disetujui! ✓',
            f"Top up sebesar Rp {data['jumlah']:,} telah disetujui. Saldo Anda telah ditambahkan.",
            data['id_request']
        )
        
        return jsonify({"status": "success", "message": "Top Up Berhasil Disetujui!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/notifications', methods=['GET'])
def get_notifications():
    """Dapatkan semua notifikasi user"""
    email = request.args.get('email')
    limit = request.args.get('limit', 10, type=int)
    
    if not email:
        return jsonify({"status": "error", "message": "Email diperlukan"}), 400
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row
            notifications = conn.execute(
                """SELECT * FROM notifications WHERE email = ? 
                   ORDER BY created_at DESC LIMIT ?""",
                (email, limit)
            ).fetchall()
        
        return jsonify({
            "status": "success",
            "notifications": [dict(n) for n in notifications]
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/notifications/unread', methods=['GET'])
def get_unread_notifications():
    """Dapatkan jumlah notifikasi yang belum dibaca"""
    email = request.args.get('email')
    
    if not email:
        return jsonify({"status": "error", "message": "Email diperlukan"}), 400
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            count = conn.execute(
                "SELECT COUNT(*) as unread FROM notifications WHERE email = ? AND is_read = 0",
                (email,)
            ).fetchone()[0]
        
        return jsonify({
            "status": "success",
            "unread_count": count
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/notifications/mark-read', methods=['POST'])
def mark_notification_read():
    """Tandai notifikasi sebagai sudah dibaca"""
    data = request.json
    notification_id = data.get('notification_id')
    
    if not notification_id:
        return jsonify({"status": "error", "message": "notification_id diperlukan"}), 400
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,)
            )
            conn.commit()
        
        return jsonify({"status": "success", "message": "Notifikasi sudah ditandai dibaca"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    """Tandai semua notifikasi sebagai sudah dibaca"""
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({"status": "error", "message": "Email diperlukan"}), 400
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE email = ? AND is_read = 0",
                (email,)
            )
            conn.commit()
        
        return jsonify({"status": "success", "message": "Semua notifikasi sudah ditandai dibaca"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/notifications/delete', methods=['DELETE'])
def delete_notification():
    """Hapus notifikasi"""
    data = request.json
    notification_id = data.get('notification_id')
    
    if not notification_id:
        return jsonify({"status": "error", "message": "notification_id diperlukan"}), 400
    
    try:
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute("DELETE FROM notifications WHERE id = ?", (notification_id,))
            conn.commit()
        
        return jsonify({"status": "success", "message": "Notifikasi dihapus"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    init_db()
    print("Server Berjalan di Port 5000...")
    app.run(host='0.0.0.0', port=5000)
