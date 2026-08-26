-- Ejecuta esto en la consola SQL de tu Postgres (Neon / Supabase / panel de Vercel Storage)
-- Es seguro correrlo aunque ya existan algunas columnas: IF NOT EXISTS evita errores.

ALTER TABLE clientes ADD COLUMN IF NOT EXISTS token_acceso TEXT;
ALTER TABLE citas ADD COLUMN IF NOT EXISTS nombre_manual TEXT;
ALTER TABLE citas ADD COLUMN IF NOT EXISTS contacto_manual TEXT;

-- Opcional pero recomendado: el token de acceso debería ser único,
-- ya que es el link personal de cada cliente.
CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_token_acceso
  ON clientes (token_acceso)
  WHERE token_acceso IS NOT NULL;

-- Verifica que todas las tablas necesarias existan (por si alguna nunca se creó):
CREATE TABLE IF NOT EXISTS usuarios_admin (
    id SERIAL PRIMARY KEY,
    usuario TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL,
    email TEXT NOT NULL,
    fecha_nacimiento TEXT NOT NULL,
    hora_nacimiento TEXT,
    lugar_nacimiento TEXT,
    motivo_consulta TEXT,
    password_hash TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    referido_por TEXT,
    token_acceso TEXT
);

CREATE TABLE IF NOT EXISTS servicios_cliente (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes (id),
    servicio_nombre TEXT
);

CREATE TABLE IF NOT EXISTS documentos (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes (id),
    nombre_archivo TEXT,
    tipo_doc TEXT,
    fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS citas (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes (id),
    servicio TEXT NOT NULL,
    fecha_cita TEXT NOT NULL,
    hora_cita TEXT NOT NULL,
    link_reunion TEXT,
    estado TEXT DEFAULT 'Pendiente',
    notas TEXT,
    nombre_manual TEXT,
    contacto_manual TEXT
);

CREATE TABLE IF NOT EXISTS solicitudes_servicio (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes (id),
    servicio_nombre TEXT NOT NULL,
    fecha_solicitud TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado TEXT DEFAULT 'Pendiente'
);

CREATE TABLE IF NOT EXISTS pagos (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes (id),
    concepto TEXT NOT NULL,
    monto REAL NOT NULL,
    fecha_pago TEXT NOT NULL,
    metodo_pago TEXT
);

CREATE TABLE IF NOT EXISTS notas_privadas (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes (id),
    contenido TEXT NOT NULL,
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
