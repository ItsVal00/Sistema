import os
import json
import sqlite3
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, Response, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'maru_secret_key_2026_astrologia')

DB_PATH = 'database.db'

# Carpeta de subida de documentos
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

# Detectar motor de base de datos
DB_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
IS_POSTGRES = bool(DB_URL)

if IS_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor


def get_db_connection():
    if IS_POSTGRES:
        db_url = DB_URL
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Decoradores de Autenticación
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Por favor inicia sesión como administrador.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


def client_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('client_logged_in'):
            flash("Inicia sesión para acceder a tu portal.", "error")
            return redirect(url_for('cliente_login'))
        return f(*args, **kwargs)
    return decorated_function


# -------------------------------------------------------------
# RUTAS PÚBLICAS Y FORMULARIO DE REGISTRO
# -------------------------------------------------------------

@app.route('/')
def index():
    # FIX: antes redirigía directo al formulario, saltándose el aviso
    # de privacidad / landing. Ahora se muestra landing.html en la raíz.
    return render_template('landing.html')


@app.route('/registro-form', methods=['GET', 'POST'])
def registro_form():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip().lower()
        fecha_nac = request.form.get('fecha_nacimiento')
        hora_nac = request.form.get('hora_nacimiento')
        lugar_nac = request.form.get('lugar_nacimiento', '').strip()
        motivo = request.form.get('motivo_consulta', '').strip()
        referido_por = request.form.get('referido_por', '').strip()
        servicios_seleccionados = request.form.getlist('servicios')
        password = request.form.get('password')

        if not nombre or not telefono or not email or not fecha_nac or not password:
            flash("Por favor completa los campos obligatorios.", "error")
            return render_template('formulario.html')

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            param_symbol = '%s' if IS_POSTGRES else '?'

            query_cliente = f'''
                INSERT INTO clientes (nombre, telefono, email, fecha_nacimiento, hora_nacimiento, lugar_nacimiento, motivo_consulta, referido_por, password_hash)
                VALUES ({param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol})
            '''
            if IS_POSTGRES:
                query_cliente += " RETURNING id"
                cursor.execute(query_cliente, (nombre, telefono, email, fecha_nac, hora_nac, lugar_nac, motivo, referido_por, password_hash))
                cliente_id = cursor.fetchone()['id']
            else:
                cursor.execute(query_cliente, (nombre, telefono, email, fecha_nac, hora_nac, lugar_nac, motivo, referido_por, password_hash))
                cliente_id = cursor.lastrowid

            for servicio in servicios_seleccionados:
                query_servicio = f'''
                    INSERT INTO servicios_cliente (cliente_id, servicio_nombre)
                    VALUES ({param_symbol}, {param_symbol})
                '''
                cursor.execute(query_servicio, (cliente_id, servicio))

            conn.commit()
            flash("¡Registro completado con éxito! Ya puedes iniciar sesión en tu portal.", "exito")
            return redirect(url_for('cliente_login'))

        except Exception as e:
            conn.rollback()
            flash(f"Ocurrió un error al registrar: {str(e)}", "error")
            return render_template('formulario.html')
        finally:
            conn.close()

    return render_template('formulario.html')


# -------------------------------------------------------------
# RUTAS DEL CLIENTE (PORTAL PRIVADO)
# -------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def cliente_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        conn = get_db_connection()
        cursor = conn.cursor()
        param_symbol = '%s' if IS_POSTGRES else '?'

        cursor.execute(f"SELECT * FROM clientes WHERE email = {param_symbol}", (email,))
        cliente = cursor.fetchone()
        conn.close()

        if cliente and check_password_hash(cliente['password_hash'], password):
            session['client_logged_in'] = True
            session['cliente_id'] = cliente['id']
            session['cliente_nombre'] = cliente['nombre']
            return redirect(url_for('mi_cuenta'))

        flash("Correo o contraseña incorrectos.", "error")

    return render_template('cliente_login.html')


@app.route('/mi-cuenta')
@client_required
def mi_cuenta():
    cliente_id = session.get('cliente_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    cursor.execute(f"SELECT * FROM clientes WHERE id = {param_symbol}", (cliente_id,))
    cliente = cursor.fetchone()

    cursor.execute(f"SELECT * FROM citas WHERE cliente_id = {param_symbol} ORDER BY fecha_cita DESC", (cliente_id,))
    citas = cursor.fetchall()

    cursor.execute(f"SELECT * FROM documentos WHERE cliente_id = {param_symbol} ORDER BY fecha_subida DESC", (cliente_id,))
    documentos = cursor.fetchall()

    cursor.execute(f"SELECT * FROM pagos WHERE cliente_id = {param_symbol} ORDER BY fecha_pago DESC", (cliente_id,))
    pagos = cursor.fetchall()

    conn.close()

    # Próxima cita (primera fecha futura) y última cita (más reciente pasada)
    hoy = datetime.now().strftime('%Y-%m-%d')
    proxima_cita = None
    ultima_cita = None
    futuras = [c for c in citas if c['fecha_cita'] and c['fecha_cita'] >= hoy]
    pasadas = [c for c in citas if c['fecha_cita'] and c['fecha_cita'] < hoy]
    if futuras:
        proxima_cita = sorted(futuras, key=lambda c: c['fecha_cita'])[0]
    if pasadas:
        ultima_cita = sorted(pasadas, key=lambda c: c['fecha_cita'], reverse=True)[0]

    # FIX: nombre de plantilla corregido (antes: 'mi_cuenta.html', que no existe)
    return render_template(
        'cliente_portal.html',
        cliente=cliente,
        citas=citas,
        documentos=documentos,
        pagos=pagos,
        proxima_cita=proxima_cita,
        ultima_cita=ultima_cita
    )


@app.route('/solicitar_servicio', methods=['POST'])
@client_required
def solicitar_servicio():
    cliente_id = session.get('cliente_id')
    servicio_nombre = request.form.get('servicio_nombre')

    if servicio_nombre:
        conn = get_db_connection()
        cursor = conn.cursor()
        param_symbol = '%s' if IS_POSTGRES else '?'

        cursor.execute(f'''
            INSERT INTO solicitudes_servicio (cliente_id, servicio_nombre)
            VALUES ({param_symbol}, {param_symbol})
        ''', (cliente_id, servicio_nombre))

        conn.commit()
        conn.close()
        flash("Solicitud enviada correctamente. Maru se pondrá en contacto contigo.", "exito")

    return redirect(url_for('mi_cuenta'))


@app.route('/logout')
def cliente_logout():
    session.pop('client_logged_in', None)
    session.pop('cliente_id', None)
    session.pop('cliente_nombre', None)
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('cliente_login'))


# -------------------------------------------------------------
# RUTAS DE ADMINISTRACIÓN
# -------------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('password', '')

        conn = get_db_connection()
        cursor = conn.cursor()
        param_symbol = '%s' if IS_POSTGRES else '?'

        cursor.execute(f"SELECT * FROM usuarios_admin WHERE usuario = {param_symbol}", (usuario,))
        admin = cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin['password_hash'], password):
            session['admin_logged_in'] = True
            session['admin_usuario'] = admin['usuario']
            return redirect(url_for('admin_dashboard'))

        flash("Credenciales de administrador inválidas.", "error")

    return render_template('admin_login.html')


@app.route('/admin')
@admin_required
def admin_dashboard():
    search_query = request.args.get('q', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    # 1. Búsqueda y Lista de Clientes
    if search_query:
        like_str = f"%{search_query}%"
        query_clientes = f'''
            SELECT * FROM clientes
            WHERE nombre LIKE {param_symbol} OR telefono LIKE {param_symbol} OR email LIKE {param_symbol} OR referido_por LIKE {param_symbol}
            ORDER BY nombre ASC
        '''
        cursor.execute(query_clientes, (like_str, like_str, like_str, like_str))
    else:
        cursor.execute("SELECT * FROM clientes ORDER BY nombre ASC")
    clientes = cursor.fetchall()

    # 2. Solicitudes Entrantes
    cursor.execute('''
        SELECT s.id, s.servicio_nombre, s.fecha_solicitud, s.estado,
               c.nombre AS cliente_nombre, c.telefono, c.email
        FROM solicitudes_servicio s
        JOIN clientes c ON s.cliente_id = c.id
        WHERE s.estado = 'Pendiente'
        ORDER BY s.fecha_solicitud DESC
    ''')
    solicitudes = cursor.fetchall()

    # 3. Citas para Calendario
    cursor.execute('''
        SELECT citas.id, citas.servicio, citas.fecha_cita, citas.hora_cita, citas.estado,
               citas.nombre_manual, citas.contacto_manual,
               clientes.nombre AS cliente_nombre
        FROM citas
        LEFT JOIN clientes ON citas.cliente_id = clientes.id
    ''')
    citas_raw = cursor.fetchall()

    citas_eventos = []
    for c in citas_raw:
        nombre_display = c['cliente_nombre'] or c['nombre_manual'] or 'Cliente General'
        citas_eventos.append({
            'id': c['id'],
            'title': f"{nombre_display} - {c['servicio']}",
            'start': f"{c['fecha_cita']}T{c['hora_cita']}",
            'backgroundColor': '#9333ea' if c['estado'] == 'Confirmada' else '#3b82f6'
        })

    # 4. Historial de Pagos
    cursor.execute('''
        SELECT pagos.*, clientes.nombre AS cliente_nombre
        FROM pagos
        JOIN clientes ON pagos.cliente_id = clientes.id
        ORDER BY fecha_pago DESC
    ''')
    pagos = cursor.fetchall()

    cursor.execute("SELECT SUM(monto) AS total FROM pagos")
    row_ingresos = cursor.fetchone()
    total_ingresos = (row_ingresos['total'] or 0) if row_ingresos else 0

    # 5. Métricas Básicas
    cursor.execute("SELECT COUNT(*) AS total FROM clientes")
    total_clientes = cursor.fetchone()['total']

    total_activos = total_clientes
    total_inactivos = 0

    # Top Servicios
    cursor.execute('''
        SELECT servicio_nombre, COUNT(*) AS total
        FROM servicios_cliente
        GROUP BY servicio_nombre
        ORDER BY total DESC LIMIT 5
    ''')
    servicios_top = cursor.fetchall()

    conn.close()

    return render_template(
        'admin_dashboard.html',
        clientes=clientes,
        solicitudes=solicitudes,
        citas_json=citas_eventos,
        pagos=pagos,
        total_ingresos=total_ingresos,
        total_clientes=total_clientes,
        total_activos=total_activos,
        total_inactivos=total_inactivos,
        servicios_top=servicios_top,
        top_signos=[],
        top_lugares=[],
        alertas=[],
        search_query=search_query
    )


@app.route('/admin/agendar_cita', methods=['POST'])
@admin_required
def agendar_cita():
    cliente_id_raw = request.form.get('cliente_id')
    nombre_manual = request.form.get('nombre_manual', '').strip()
    contacto_manual = request.form.get('contacto_manual', '').strip()

    servicio = request.form.get('servicio')
    fecha = request.form.get('fecha_cita')
    hora = request.form.get('hora_cita')
    link = request.form.get('link_reunion', '').strip()
    notas = request.form.get('notas', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    if not cliente_id_raw or cliente_id_raw == "manual":
        cursor.execute(f'''
            INSERT INTO citas (cliente_id, servicio, fecha_cita, hora_cita, link_reunion, notas, nombre_manual, contacto_manual)
            VALUES (NULL, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol})
        ''', (servicio, fecha, hora, link, notas, nombre_manual, contacto_manual))
    else:
        try:
            cliente_id = int(cliente_id_raw)
        except ValueError:
            cliente_id = None

        cursor.execute(f'''
            INSERT INTO citas (cliente_id, servicio, fecha_cita, hora_cita, link_reunion, notas)
            VALUES ({param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol})
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
    metodo = request.form.get('metodo_pago')
    fecha = request.form.get('fecha_pago')

    if cliente_id and concepto and monto and fecha:
        conn = get_db_connection()
        cursor = conn.cursor()
        param_symbol = '%s' if IS_POSTGRES else '?'

        cursor.execute(f'''
            INSERT INTO pagos (cliente_id, concepto, monto, fecha_pago, metodo_pago)
            VALUES ({param_symbol}, {param_symbol}, {param_symbol}, {param_symbol}, {param_symbol})
        ''', (cliente_id, concepto, float(monto), fecha, metodo))

        conn.commit()
        conn.close()
        flash("Pago registrado correctamente.", "exito")

    return redirect(url_for('admin_dashboard'))


@app.route('/admin/estado_solicitud/<int:solicitud_id>/<estado>')
@admin_required
def estado_solicitud(solicitud_id, estado):
    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    cursor.execute(f"UPDATE solicitudes_servicio SET estado = {param_symbol} WHERE id = {param_symbol}", (estado, solicitud_id))
    conn.commit()
    conn.close()
    flash("Estado de solicitud actualizado.", "exito")
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/cliente/<int:cliente_id>')
@admin_required
def admin_cliente_detalle(cliente_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    cursor.execute(f"SELECT * FROM clientes WHERE id = {param_symbol}", (cliente_id,))
    cliente = cursor.fetchone()

    if not cliente:
        conn.close()
        flash("Cliente no encontrado.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor.execute(f"SELECT * FROM servicios_cliente WHERE cliente_id = {param_symbol}", (cliente_id,))
    servicios_rows = cursor.fetchall()
    servicios = [s['servicio_nombre'] for s in servicios_rows]

    cursor.execute(f"SELECT * FROM citas WHERE cliente_id = {param_symbol} ORDER BY fecha_cita DESC", (cliente_id,))
    citas = cursor.fetchall()

    cursor.execute(f"SELECT * FROM documentos WHERE cliente_id = {param_symbol} ORDER BY fecha_subida DESC", (cliente_id,))
    documentos = cursor.fetchall()

    cursor.execute(f"SELECT * FROM pagos WHERE cliente_id = {param_symbol} ORDER BY fecha_pago DESC", (cliente_id,))
    pagos = cursor.fetchall()

    cursor.execute(f"SELECT * FROM notas_privadas WHERE cliente_id = {param_symbol} ORDER BY fecha DESC", (cliente_id,))
    notas = cursor.fetchall()

    conn.close()

    # FIX: nombre de plantilla corregido (antes: 'admin_cliente_detalle.html', que no existe)
    return render_template(
        'cliente_detalle.html',
        cliente=cliente,
        servicios=servicios,
        citas=citas,
        documentos=documentos,
        pagos=pagos,
        notas=notas
    )


@app.route('/admin/guardar_nota', methods=['POST'])
@admin_required
def guardar_nota():
    cliente_id = request.form.get('cliente_id')
    contenido = request.form.get('contenido', '').strip()

    if cliente_id and contenido:
        conn = get_db_connection()
        cursor = conn.cursor()
        param_symbol = '%s' if IS_POSTGRES else '?'

        cursor.execute(f"INSERT INTO notas_privadas (cliente_id, contenido) VALUES ({param_symbol}, {param_symbol})", (cliente_id, contenido))
        conn.commit()
        conn.close()
        flash("Nota privada guardada.", "exito")

    return redirect(url_for('admin_cliente_detalle', cliente_id=cliente_id))


# -------------------------------------------------------------
# DOCUMENTOS: SUBIR / VER / ELIMINAR (rutas nuevas)
# -------------------------------------------------------------

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/admin/subir_documento/<int:cliente_id>', methods=['POST'])
@admin_required
def subir_documento(cliente_id):
    tipo_doc = request.form.get('tipo_doc')
    archivo = request.files.get('archivo')

    if not archivo or archivo.filename == '':
        flash("Debes seleccionar un archivo.", "error")
        return redirect(url_for('admin_cliente_detalle', cliente_id=cliente_id))

    if not allowed_file(archivo.filename):
        flash("Tipo de archivo no permitido (solo PDF, PNG, JPG).", "error")
        return redirect(url_for('admin_cliente_detalle', cliente_id=cliente_id))

    filename = secure_filename(archivo.filename)
    filename = f"{cliente_id}_{int(datetime.now().timestamp())}_{filename}"
    archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    cursor.execute(f'''
        INSERT INTO documentos (cliente_id, tipo_doc, nombre_archivo)
        VALUES ({param_symbol}, {param_symbol}, {param_symbol})
    ''', (cliente_id, tipo_doc, filename))

    conn.commit()
    conn.close()

    flash("Documento subido correctamente.", "exito")
    return redirect(url_for('admin_cliente_detalle', cliente_id=cliente_id))


@app.route('/admin/eliminar_documento/<int:doc_id>', methods=['POST'])
@admin_required
def eliminar_documento(doc_id):
    cliente_id = request.form.get('cliente_id')
    password = request.form.get('password', '')

    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    # Valida la clave contra el usuario admin actualmente logueado
    cursor.execute(f"SELECT * FROM usuarios_admin WHERE usuario = {param_symbol}", (session.get('admin_usuario'),))
    admin = cursor.fetchone()

    if not admin or not check_password_hash(admin['password_hash'], password):
        conn.close()
        flash("Clave incorrecta. No se eliminó el documento.", "error")
        return redirect(url_for('admin_cliente_detalle', cliente_id=cliente_id))

    cursor.execute(f"SELECT * FROM documentos WHERE id = {param_symbol}", (doc_id,))
    doc = cursor.fetchone()

    if doc:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc['nombre_archivo'])
        if os.path.exists(filepath):
            os.remove(filepath)
        cursor.execute(f"DELETE FROM documentos WHERE id = {param_symbol}", (doc_id,))
        conn.commit()
        flash("Documento eliminado correctamente.", "exito")
    else:
        flash("Documento no encontrado.", "error")

    conn.close()
    return redirect(url_for('admin_cliente_detalle', cliente_id=cliente_id))


@app.route('/crear-admin-init')
def crear_admin_init():
    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    pwd_hash = generate_password_hash("maru2026")

    cursor.execute(f"DELETE FROM usuarios_admin WHERE usuario = {param_symbol}", ('admin',))
    cursor.execute(f"INSERT INTO usuarios_admin (usuario, password_hash) VALUES ({param_symbol}, {param_symbol})", ('admin', pwd_hash))

    conn.commit()
    conn.close()
    return "OK: Usuario admin restaurado con clave maru2026"


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_usuario', None)
    flash("Has cerrado sesión como administrador.", "info")
    return redirect(url_for('admin_login'))


# Exportaciones a CSV
@app.route('/admin/exportar_clientes')
@admin_required
def exportar_clientes():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre, telefono, email, fecha_nacimiento, lugar_nacimiento, referido_por FROM clientes")
    clientes = cursor.fetchall()
    conn.close()

    csv_data = "Nombre,Telefono,Email,Fecha_Nacimiento,Lugar_Nacimiento,Referido_Por\n"
    for c in clientes:
        csv_data += f'"{c["nombre"]}","{c["telefono"]}","{c["email"]}","{c["fecha_nacimiento"]}","{c["lugar_nacimiento"] or ""}","{c["referido_por"] or ""}"\n'

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=consultantes_maru.csv"}
    )


@app.route('/admin/exportar_pagos')
@admin_required
def exportar_pagos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT clientes.nombre, pagos.concepto, pagos.monto, pagos.metodo_pago, pagos.fecha_pago
        FROM pagos JOIN clientes ON pagos.cliente_id = clientes.id ORDER BY fecha_pago DESC
    ''')
    pagos = cursor.fetchall()
    conn.close()

    csv_data = "Cliente,Concepto,Monto,Metodo,Fecha\n"
    for p in pagos:
        csv_data += f'"{p["nombre"]}","{p["concepto"]}","{p["monto"]}","{p["metodo_pago"]}","{p["fecha_pago"]}"\n'

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=reporte_pagos_maru.csv"}
    )


@app.route('/admin/eliminar_cita/<int:cita_id>')
@admin_required
def eliminar_cita(cita_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    param_symbol = '%s' if IS_POSTGRES else '?'

    cursor.execute(f"DELETE FROM citas WHERE id = {param_symbol}", (cita_id,))
    conn.commit()
    conn.close()

    flash("Cita eliminada correctamente de la agenda.", "exito")
    return redirect(url_for('admin_dashboard'))


if __name__ == '__main__':
    app.run(debug=True)