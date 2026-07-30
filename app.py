from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session, Response
import sqlite3
import os
import csv
import io
import smtplib
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import Counter
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = 'clave_secreta_para_sesion_de_maru'
ADMIN_DELETE_PASSWORD = "1234"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_EMISOR = "tu_correo@gmail.com"
EMAIL_PASSWORD = "tu_app_password"

# --- CONFIGURACIÓN DE RUTA SEGURA PARA VERCEL (Read-Only Filesystem) ---
if os.environ.get('VERCEL'):
    DB_PATH = os.path.join(tempfile.gettempdir(), 'database.db')
    UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'uploads')
else:
    DB_PATH = 'database.db'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Debes iniciar sesión para acceder al Panel Administrativo.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def obtener_signo_zodiacal(fecha_str):
    try:
        fn = datetime.strptime(fecha_str, '%Y-%m-%d')
        dia, mes = fn.day, fn.month
        if (mes == 3 and dia >= 21) or (mes == 4 and dia <= 19): return "Aries"
        if (mes == 4 and dia >= 20) or (mes == 5 and dia <= 20): return "Tauro"
        if (mes == 5 and dia >= 21) or (mes == 6 and dia <= 20): return "Géminis"
        if (mes == 6 and dia >= 21) or (mes == 7 and dia <= 22): return "Cáncer"
        if (mes == 7 and dia >= 23) or (mes == 8 and dia <= 22): return "Leo"
        if (mes == 8 and dia >= 23) or (mes == 9 and dia <= 22): return "Virgo"
        if (mes == 9 and dia >= 23) or (mes == 10 and dia <= 22): return "Libra"
        if (mes == 10 and dia >= 23) or (mes == 11 and dia <= 21): return "Escorpio"
        if (mes == 11 and dia >= 22) or (mes == 12 and dia <= 21): return "Sagitario"
        if (mes == 12 and dia >= 22) or (mes == 1 and dia <= 19): return "Capricornio"
        if (mes == 1 and dia >= 20) or (mes == 2 and dia <= 18): return "Acuario"
        if (mes == 2 and dia >= 19) or (mes == 3 and dia <= 20): return "Piscis"
    except:
        return "Desconocido"
    return "Desconocido"

def enviar_notificacion_email(destinatario, nombre_cliente, tipo_doc):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_EMISOR
        msg['To'] = destinatario
        msg['Subject'] = f"✨ Tu documento ({tipo_doc}) está listo — Maru González"

        cuerpo = f"""
        Hola {nombre_cliente},

        Te informamos que Maru ha subido un nuevo documento a tu portal astrológico:
        📄 Documento: {tipo_doc}

        Puedes acceder y descargarlo ingresando a tu portal.

        Bendiciones,
        Maru González — Astrología Evolutiva
        """
        msg.attach(MIMEText(cuerpo, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_EMISOR, EMAIL_PASSWORD)
        server.sendmail(EMAIL_EMISOR, destinatario, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"No se pudo enviar el correo: {e}")

# --- BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios_admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    cursor.execute("SELECT * FROM usuarios_admin WHERE usuario = 'admin'")
    if not cursor.fetchone():
        pwd_hash = generate_password_hash("maru2026")
        cursor.execute("INSERT INTO usuarios_admin (usuario, password_hash) VALUES (?, ?)", ("admin", pwd_hash))

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            email TEXT NOT NULL,
            fecha_nacimiento TEXT NOT NULL,
            hora_nacimiento TEXT,
            lugar_nacimiento TEXT,
            motivo_consulta TEXT,
            referido_por TEXT,
            password_hash TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute("PRAGMA table_info(clientes)")
    columnas = [column[1] for column in cursor.fetchall()]
    if 'password_hash' not in columnas:
        cursor.execute("ALTER TABLE clientes ADD COLUMN password_hash TEXT")
    if 'referido_por' not in columnas:
        cursor.execute("ALTER TABLE clientes ADD COLUMN referido_por TEXT")

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicios_cliente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            servicio_nombre TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            nombre_archivo TEXT,
            tipo_doc TEXT,
            fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS citas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            servicio TEXT NOT NULL,
            fecha_cita TEXT NOT NULL,
            hora_cita TEXT NOT NULL,
            link_reunion TEXT,
            estado TEXT DEFAULT 'Pendiente',
            notas TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS solicitudes_servicio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            servicio_nombre TEXT NOT NULL,
            fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            estado TEXT DEFAULT 'Pendiente',
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            concepto TEXT NOT NULL,
            monto REAL NOT NULL,
            fecha_pago TEXT NOT NULL,
            metodo_pago TEXT,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas_privadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            contenido TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()


# --- RUTAS PÚBLICAS Y CLIENTE ---

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/registro-form')
def formulario():
    return render_template('formulario.html')

@app.route('/registro', methods=['POST'])
def registrar_cliente():
    nombre = request.form.get('nombre')
    telefono = request.form.get('telefono', '').strip()
    email = request.form.get('email', '').strip().lower()
    fecha_nac = request.form.get('fecha_nacimiento')
    hora_nac = request.form.get('hora_nacimiento')
    lugar_nac = request.form.get('lugar_nacimiento')
    motivo = request.form.get('motivo_consulta')
    referido_por = request.form.get('referido_por', '').strip()
    password = request.form.get('password', '').strip()
    
    servicios_seleccionados = request.form.getlist('servicios')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    pwd_hash = generate_password_hash(password) if password else None

    cursor.execute('''
        INSERT INTO clientes (nombre, telefono, email, fecha_nacimiento, hora_nacimiento, lugar_nacimiento, motivo_consulta, referido_por, password_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (nombre, telefono, email, fecha_nac, hora_nac, lugar_nac, motivo, referido_por, pwd_hash))
    
    cliente_id = cursor.lastrowid
    for servicio in servicios_seleccionados:
        cursor.execute('INSERT INTO servicios_cliente (cliente_id, servicio_nombre) VALUES (?, ?)', (cliente_id, servicio))
        
    conn.commit()
    conn.close()
    
    session['cliente_id'] = cliente_id
    return redirect(url_for('portal_cliente'))

@app.route('/mi-cuenta', methods=['GET', 'POST'])
def portal_cliente():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        identificador = request.form.get('identificador', '').strip().lower()
        password = request.form.get('password', '').strip()

        cursor.execute("SELECT * FROM clientes WHERE LOWER(email) = ? OR telefono = ?", (identificador, identificador))
        cliente = cursor.fetchone()
        
        if cliente:
            if cliente['password_hash']:
                if check_password_hash(cliente['password_hash'], password):
                    session['cliente_id'] = cliente['id']
                else:
                    flash("Contraseña incorrecta.", "error")
                    conn.close()
                    return render_template('cliente_login.html')
            else:
                session['cliente_id'] = cliente['id']
        else:
            flash("No encontramos ningún registro con ese correo o WhatsApp.", "error")
            conn.close()
            return render_template('cliente_login.html')

    cliente_id = session.get('cliente_id')
    if not cliente_id:
        conn.close()
        return render_template('cliente_login.html')

    cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
    cliente = cursor.fetchone()

    if not cliente:
        session.pop('cliente_id', None)
        conn.close()
        flash("Sesión caducada o registro no encontrado.", "error")
        return render_template('cliente_login.html')

    cursor.execute("SELECT * FROM documentos WHERE cliente_id = ? ORDER BY id DESC", (cliente_id,))
    documentos = cursor.fetchall()

    cursor.execute("SELECT * FROM citas WHERE cliente_id = ? AND estado = 'Pendiente' ORDER BY fecha_cita ASC, hora_cita ASC LIMIT 1", (cliente_id,))
    proxima_cita = cursor.fetchone()

    cursor.execute("SELECT * FROM citas WHERE cliente_id = ? AND estado = 'Completada' ORDER BY fecha_cita DESC LIMIT 1", (cliente_id,))
    ultima_cita = cursor.fetchone()

    conn.close()
    return render_template('cliente_portal.html', cliente=cliente, documentos=documentos, proxima_cita=proxima_cita, ultima_cita=ultima_cita)

@app.route('/solicitar-servicio', methods=['POST'])
def solicitar_servicio():
    cliente_id = session.get('cliente_id')
    if not cliente_id:
        return redirect(url_for('portal_cliente'))
    
    servicio_nombre = request.form.get('servicio_nombre')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO solicitudes_servicio (cliente_id, servicio_nombre) VALUES (?, ?)', (cliente_id, servicio_nombre))
    conn.commit()
    conn.close()
    
    flash(f"¡Solicitud enviada para '{servicio_nombre}'!", "exito")
    return redirect(url_for('portal_cliente'))

@app.route('/logout-cliente')
def logout_cliente():
    session.pop('cliente_id', None)
    return redirect(url_for('portal_cliente'))


# --- RUTAS DE AUTENTICACIÓN ADMIN ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('password', '').strip()
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios_admin WHERE usuario = ?", (usuario,))
        user_row = cursor.fetchone()
        conn.close()

        if user_row and check_password_hash(user_row['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_usuario'] = usuario
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Usuario o contraseña incorrectos.", "error")

    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_usuario', None)
    flash("Has cerrado sesión.", "exito")
    return redirect(url_for('admin_login'))


# --- RUTAS ADMIN ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    search_query = request.args.get('q', '').strip()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if search_query:
        cursor.execute("SELECT * FROM clientes WHERE nombre LIKE ? OR telefono LIKE ? OR email LIKE ? OR referido_por LIKE ? ORDER BY id DESC", 
                       (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute("SELECT * FROM clientes ORDER BY id DESC")
    clientes = [dict(row) for row in cursor.fetchall()]
    
    hoy = datetime.now().date()
    alertas_cumple = []
    signos_lista = []
    lugares_lista = []
    
    for c in clientes:
        signo = obtener_signo_zodiacal(c['fecha_nacimiento'])
        signos_lista.append(signo)
        
        if c['lugar_nacimiento']:
            lugares_lista.append(c['lugar_nacimiento'].title().strip())

        try:
            fn = datetime.strptime(c['fecha_nacimiento'], '%Y-%m-%d').date()
            cumple_este_anio = fn.replace(year=hoy.year)
            if cumple_este_anio < hoy:
                cumple_este_anio = fn.replace(year=hoy.year + 1)
            dias_faltantes = (cumple_este_anio - hoy).days
            if 0 <= dias_faltantes <= 30:
                c_dict = dict(c)
                c_dict['dias_faltantes'] = dias_faltantes
                c_dict['fecha_cumple'] = cumple_este_anio.strftime('%d/%m')
                alertas_cumple.append(c_dict)
        except:
            pass

    cursor.execute('''
        SELECT c.*, cl.nombre as cliente_nombre 
        FROM citas c 
        JOIN clientes cl ON c.cliente_id = cl.id 
        ORDER BY c.fecha_cita ASC, c.hora_cita ASC
    ''')
    todas_citas = [dict(r) for r in cursor.fetchall()]

    citas_json = []
    for cita in todas_citas:
        citas_json.append({
            'title': f"{cita['cliente_nombre']} - {cita['servicio']}",
            'start': f"{cita['fecha_cita']}T{cita['hora_cita']}",
            'color': '#22c55e' if cita['estado'] == 'Completada' else '#a855f7'
        })

    cursor.execute('''
        SELECT s.*, c.nombre as cliente_nombre, c.telefono, c.email 
        FROM solicitudes_servicio s
        JOIN clientes c ON s.cliente_id = c.id
        WHERE s.estado = 'Pendiente'
        ORDER BY s.id DESC
    ''')
    solicitudes = cursor.fetchall()

    cursor.execute("SELECT servicio_nombre, COUNT(*) as total FROM servicios_cliente GROUP BY servicio_nombre ORDER BY total DESC LIMIT 5")
    servicios_top = cursor.fetchall()

    cursor.execute('''
        SELECT p.*, c.nombre as cliente_nombre 
        FROM pagos p 
        JOIN clientes c ON p.cliente_id = c.id 
        ORDER BY p.fecha_pago DESC
    ''')
    pagos_lista = cursor.fetchall()

    cursor.execute("SELECT SUM(monto) as total FROM pagos")
    total_ingresos = cursor.fetchone()['total'] or 0.0

    hace_6_meses = (hoy - timedelta(days=180)).strftime('%Y-%m-%d')
    cursor.execute("SELECT DISTINCT cliente_id FROM citas WHERE fecha_cita >= ?", (hace_6_meses,))
    activos_citas = {r['cliente_id'] for r in cursor.fetchall()}
    cursor.execute("SELECT DISTINCT cliente_id FROM pagos WHERE fecha_pago >= ?", (hace_6_meses,))
    activos_pagos = {r['cliente_id'] for r in cursor.fetchall()}
    
    activos_ids = activos_citas.union(activos_pagos)
    total_clientes = len(clientes)
    total_activos = len(activos_ids)
    total_inactivos = max(0, total_clientes - total_activos)

    top_signos = Counter(signos_lista).most_common(5)
    top_lugares = Counter(lugares_lista).most_common(5)

    conn.close()
    
    return render_template('admin_dashboard.html', 
                           clientes=clientes, 
                           search_query=search_query,
                           alertas=alertas_cumple, 
                           citas=todas_citas,
                           citas_json=citas_json,
                           solicitudes=solicitudes,
                           servicios_top=servicios_top,
                           pagos=pagos_lista,
                           total_ingresos=total_ingresos,
                           total_clientes=total_clientes,
                           total_activos=total_activos,
                           total_inactivos=total_inactivos,
                           top_signos=top_signos,
                           top_lugares=top_lugares)

@app.route('/admin/exportar_clientes')
@admin_required
def exportar_clientes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, telefono, email, fecha_nacimiento, hora_nacimiento, lugar_nacimiento, referido_por, fecha_registro FROM clientes")
    filas = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nombre', 'Telefono', 'Email', 'Fecha Nacimiento', 'Hora', 'Lugar', 'Referido Por', 'Fecha Registro'])
    writer.writerows(filas)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=reporte_clientes.csv"}
    )

@app.route('/admin/exportar_pagos')
@admin_required
def exportar_pagos():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, c.nombre, p.concepto, p.monto, p.metodo_pago, p.fecha_pago 
        FROM pagos p JOIN clientes c ON p.cliente_id = c.id
    ''')
    filas = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID Pago', 'Cliente', 'Concepto', 'Monto ($)', 'Metodo', 'Fecha'])
    writer.writerows(filas)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=reporte_facturacion.csv"}
    )

@app.route('/admin/cliente/<int:cliente_id>')
@admin_required
def cliente_detalle(cliente_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
    cliente = cursor.fetchone()
    
    if not cliente:
        conn.close()
        flash("El cliente consultado no existe o fue eliminado.", "error")
        return redirect(url_for('admin_dashboard'))
    
    cursor.execute("SELECT servicio_nombre FROM servicios_cliente WHERE cliente_id = ?", (cliente_id,))
    servicios = [row['servicio_nombre'] for row in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM documentos WHERE cliente_id = ? ORDER BY id DESC", (cliente_id,))
    documentos = cursor.fetchall()

    cursor.execute("SELECT * FROM citas WHERE cliente_id = ? ORDER BY fecha_cita DESC", (cliente_id,))
    historial_citas = cursor.fetchall()
    
    cursor.execute("SELECT * FROM pagos WHERE cliente_id = ? ORDER BY fecha_pago DESC", (cliente_id,))
    historial_pagos = cursor.fetchall()

    cursor.execute("SELECT * FROM notas_privadas WHERE cliente_id = ? ORDER BY id DESC", (cliente_id,))
    notas_privadas = cursor.fetchall()
    
    conn.close()
    return render_template('cliente_detalle.html', cliente=cliente, servicios=servicios, documentos=documentos, citas=historial_citas, pagos=historial_pagos, notas=notas_privadas)

@app.route('/admin/guardar_nota/<int:cliente_id>', methods=['POST'])
@admin_required
def guardar_nota(cliente_id):
    contenido = request.form.get('contenido')
    if contenido:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO notas_privadas (cliente_id, contenido) VALUES (?, ?)", (cliente_id, contenido))
        conn.commit()
        conn.close()
        flash("Nota privada guardada.", "exito")
    return redirect(url_for('cliente_detalle', cliente_id=cliente_id))

@app.route('/admin/agendar_cita', methods=['POST'])
@admin_required
def agendar_cita():
    cliente_id = request.form.get('cliente_id') # Puede venir vacío si es manual
    nombre_manual = request.form.get('nombre_manual', '').strip()
    contacto_manual = request.form.get('contacto_manual', '').strip()
    
    servicio = request.form.get('servicio')
    fecha = request.form.get('fecha_cita')
    hora = request.form.get('hora_cita')
    link = request.form.get('link_reunion')
    notas = request.form.get('notas', '')

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Si seleccionó "Cliente no registrado / Manual"
    if not cliente_id or cliente_id == "manual":
        cursor.execute('''
            INSERT INTO citas (cliente_id, servicio, fecha_cita, hora_cita, link_reunion, notas, nombre_manual, contacto_manual) 
            VALUES (NULL, %, %, %, %, %, %, %)
        ''', (servicio, fecha, hora, link, notas, nombre_manual, contacto_manual))
    else:
        cursor.execute('''
            INSERT INTO citas (cliente_id, servicio, fecha_cita, hora_cita, link_reunion, notas) 
            VALUES (%, %, %, %, %, %)
        ''', (cliente_id, servicio, fecha, hora, link, notas))
        
    conn.commit()
    conn.close()
    flash("Cita agendada correctamente.", "exito")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/registrar_pago', methods=['POST'])
@admin_required
def registrar_pago():
    cliente_id = request.form.get('cliente_id')
    concepto = request.form.get('concepto')
    monto = request.form.get('monto')
    fecha_pago = request.form.get('fecha_pago')
    metodo_pago = request.form.get('metodo_pago')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pagos (cliente_id, concepto, monto, fecha_pago, metodo_pago) VALUES (?, ?, ?, ?, ?)', (cliente_id, concepto, monto, fecha_pago, metodo_pago))
    conn.commit()
    conn.close()
    flash("Pago registrado.", "exito")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/estado_cita/<int:cita_id>/<string:nuevo_estado>')
@admin_required
def cambiar_estado_cita(cita_id, nuevo_estado):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE citas SET estado = ? WHERE id = ?", (nuevo_estado, cita_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/estado_solicitud/<int:solicitud_id>/<string:nuevo_estado>')
@admin_required
def cambiar_estado_solicitud(solicitud_id, nuevo_estado):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE solicitudes_servicio SET estado = ? WHERE id = ?", (nuevo_estado, solicitud_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/subir_documento/<int:cliente_id>', methods=['POST'])
@admin_required
def subir_documento(cliente_id):
    if 'archivo' not in request.files: return redirect(request.url)
    file = request.files['archivo']
    tipo_doc = request.form.get('tipo_doc')
    if file and allowed_file(file.filename):
        filename = f"{cliente_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('INSERT INTO documentos (cliente_id, nombre_archivo, tipo_doc) VALUES (?, ?, ?)', (cliente_id, filename, tipo_doc))
        
        cursor.execute("SELECT nombre, email FROM clientes WHERE id = ?", (cliente_id,))
        cli = cursor.fetchone()
        conn.commit()
        conn.close()

        if cli and cli['email']:
            enviar_notificacion_email(cli['email'], cli['nombre'], tipo_doc)

        flash("Documento subido con éxito y notificación enviada.", "exito")
    return redirect(url_for('cliente_detalle', cliente_id=cliente_id))

@app.route('/admin/eliminar_documento/<int:doc_id>', methods=['POST'])
@admin_required
def eliminar_documento(doc_id):
    password = request.form.get('password')
    cliente_id = request.form.get('cliente_id')
    if password != ADMIN_DELETE_PASSWORD:
        flash("Contraseña incorrecta.", "error")
        return redirect(url_for('cliente_detalle', cliente_id=cliente_id))
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT nombre_archivo FROM documentos WHERE id = ?", (doc_id,))
    doc = cursor.fetchone()
    if doc:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc['nombre_archivo'])
        if os.path.exists(filepath): os.remove(filepath)
        cursor.execute("DELETE FROM documentos WHERE id = ?", (doc_id,))
        conn.commit()
        flash("Archivo eliminado.", "exito")
    conn.close()
    return redirect(url_for('cliente_detalle', cliente_id=cliente_id))

@app.route('/uploads/<filename>')
def descargar_archivo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)