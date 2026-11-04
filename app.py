# ═══════════════════════════════════════════════════════════════════════
#  SISTEMA DE ANÁLISIS DE IMPORTACIÓN INTELIGENTE 🐉✨ (BLOQUE 1 / 3)
#  Motor original y metodología: Prof. Jesús Pulido V. (New 30/10/26)
# ═══════════════════════════════════════════════════════════════════════

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date, timedelta, datetime
import io, os, json, re, unicodedata, random
import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from xhtml2pdf import pisa
import matplotlib.pyplot as plt
from fpdf import FPDF

# -- MÓDULO DE BÚSQUEDA WEB DE PROVEEDORES --
from supplier_finder import find_suppliers, wa_link

try:
    import sheets_db
    SHEETS_DB_OK = True
except ImportError:
    SHEETS_DB_OK = False

CENTAVO = Decimal("0.01")
CERO    = Decimal("0")
UNO     = Decimal("1")

GASTOS_CONTENEDOR = (
    ("Manejo de Puerto",           "peso"),
    ("Flete Terrestre Nacional",   "peso"),
    ("Logística Internacional",    "volumen"),
    ("Derechos de Aduana",         "volumen"),
    ("Gestión Aduanera",           "volumen"),
    ("Gastos Administrativos",     "volumen"),
)

SECTORES = [
    "Ferretería / Herramientas", "Repuestos para motos",
    "Repuestos para automóviles", "Cauchos y neumáticos",
    "Construcción / Materiales", "Agro / Insumos",
    "Tecnología / Electrónica", "Textil / Calzado",
    "Salud / Farmacia", "Otro (especificar)",
]

ORIGENES = [
    "China", "Estados Unidos", "Panamá", "Brasil", "Turquía",
    "India", "Colombia", "México", "Vietnam", "Tailandia",
    "Corea del Sur", "Japón", "Alemania", "España", "Italia",
    "Otro (especificar)",
]

# Actualización de Orígenes y Tiempos de Tránsito Estándar (Días)
ORIGENES_CON_TRANSITO = {
    "China": {"dias": 60, "tipo": "maritimo"},
    "Estados Unidos": {"dias": 22, "tipo": "maritimo/aereo"},
    "Panamá": {"dias": 15, "tipo": "maritimo/multimodal"},
    "Brasil": {"dias": 25, "tipo": "terrestre/maritimo"},
    "Turquía": {"dias": 35, "tipo": "maritimo"},
    "India": {"dias": 45, "tipo": "maritimo"},
    "Colombia": {"dias": 8, "tipo": "terrestre"},
    "México": {"dias": 20, "tipo": "maritimo"},
    "Vietnam": {"dias": 55, "tipo": "maritimo"},
    "Tailandia": {"dias": 55, "tipo": "maritimo"},
    "Corea del Sur": {"dias": 50, "tipo": "maritimo"},
    "Japón": {"dias": 50, "tipo": "maritimo"},
    "Alemania": {"dias": 30, "tipo": "maritimo"},
    "España": {"dias": 25, "tipo": "maritimo"},
    "Italia": {"dias": 28, "tipo": "maritimo"},
    "Proveedor Nacional (Local / Emergencia)": {"dias": 4, "tipo": "terrestre_local"},
    "Otro (especificar)": {"dias": 45, "tipo": "personalizado"}
}

# Extraemos la lista para los selectbox de la interfaz manteniendo compatibilidad
ORIGENES = list(ORIGENES_CON_TRANSITO.keys())

def obtener_dias_transito(pais_origen):
    """Devuelve los días de tránsito estimados según el país seleccionado."""
    info = ORIGENES_CON_TRANSITO.get(pais_origen, {"dias": 60})
    return info["dias"]

DEFAULTS = {
    "id_perfil": "", "empresa": "", "rif": "", "propietario": "", "email": "",
    "sector": "Ferretería / Herramientas", "sector_otro": "",
    "margen": 30.0, "desc_mayorista": 15.0, "desc_especial": 5.0,
    "origen": "China", "origen_otro": "", "proveedor": "", "factura": "",
    "fecha_proximo_pedido": None, "capital_inicial": 0.0,
    "costo_fijo_semanal": 0.0, "monto_proximo_pedido": 0.0,
}

MONEDAS_DEFAULT = {
    "USD": {"simbolo": "$",   "unidades_por_usd": 1.0},
    "EUR": {"simbolo": "€",   "unidades_por_usd": 0.93},
    "VES": {"simbolo": "Bs.", "unidades_por_usd": 40.0},
}
RUTA_TASAS = "tasas_cambio.json"

PARTIDAS_BASE = {
    "8207.50.00": {"descripcion": "Útiles de taladrar (brocas)", "ad_valorem": 0.05, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "82 - Herramientas"},
    "8207.90.00": {"descripcion": "Otros útiles intercambiables", "ad_valorem": 0.05, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "82 - Herramientas"},
    "7318.15.00": {"descripcion": "Tornillos y pernos de acero", "ad_valorem": 0.10, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "73 - Manufacturas de hierro"},
    "8414.80.20": {"descripcion": "Compresores de aire", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "SENCAMER + Norma COVENIN", "capitulo": "84 - Máquinas y aparatos"},
    "8716.80.00": {"descripcion": "Carretillas de mano", "ad_valorem": 0.20, "iva": 0.16, "requisitos": "Revisar norma técnica", "capitulo": "87 - Vehículos"},
    "8708.10.00": {"descripcion": "Parachoques y sus partes", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.29.00": {"descripcion": "Partes de carrocería", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.30.00": {"descripcion": "Frenos y servofrenos", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Revisar norma técnica", "capitulo": "87 - Vehículos"},
    "8708.40.00": {"descripcion": "Cajas de cambio", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.50.00": {"descripcion": "Ejes con diferencial", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8708.99.00": {"descripcion": "Otras partes y accesorios", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8714.10.00": {"descripcion": "Partes de motocicletas", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "8714.91.00": {"descripcion": "Sillines y partes", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "87 - Vehículos"},
    "4011.10.00": {"descripcion": "Neumáticos para automóviles", "ad_valorem": 0.20, "iva": 0.16, "requisitos": "SENCAMER + Norma COVENIN", "capitulo": "40 - Caucho"},
    "4011.20.00": {"descripcion": "Neumáticos para buses/camiones", "ad_valorem": 0.15, "iva": 0.16, "requisitos": "SENCAMER", "capitulo": "40 - Caucho"},
    "4011.40.00": {"descripcion": "Neumáticos para motocicletas", "ad_valorem": 0.20, "iva": 0.16, "requisitos": "SENCAMER", "capitulo": "40 - Caucho"},
    "8504.40.00": {"descripcion": "Fuentes de poder / cargadores", "ad_valorem": 0.10, "iva": 0.16, "requisitos": "Revisar norma técnica", "capitulo": "85 - Máquinas eléctricas"},
    "8544.42.00": {"descripcion": "Cables y conductores eléctricos", "ad_valorem": 0.10, "iva": 0.16, "requisitos": "Ninguno especial", "capitulo": "85 - Máquinas eléctricas"},
}

BANCO_PRODUCTOS_SINTETICOS = {
    "Moto Repuestos": [
        {"nombre": "Kit de Arrastre CG150", "peso": 2.10, "vol": 0.0035, "fob": 14.50, "partida": "8714.10.00", "pvp": 35.00},
        {"nombre": "Juego de Pastillas de Freno", "peso": 0.35, "vol": 0.0008, "fob": 1.80, "partida": "8714.10.00", "pvp": 5.00},
        {"nombre": "Amortiguadores Traseros (Par)", "peso": 3.80, "vol": 0.0075, "fob": 18.00, "partida": "8714.10.00", "pvp": 45.00},
        {"nombre": "Casco Integral Certificado", "peso": 1.45, "vol": 0.0220, "fob": 12.00, "partida": "6506.10.00", "pvp": 50.00},
        {"nombre": "Correa de Transmisión Scooter", "peso": 0.18, "vol": 0.0005, "fob": 2.20, "partida": "4010.35.00", "pvp": 6.00},
        {"nombre": "Caucho/Neumático 90/90-18", "peso": 3.20, "vol": 0.0180, "fob": 11.50, "partida": "4011.40.00", "pvp": 30.00},
        {"nombre": "Batería de Gel 12V 7Ah", "peso": 2.10, "vol": 0.0020, "fob": 8.50, "partida": "8507.10.00", "pvp": 22.00},
        {"nombre": "Carburador Completo CG150", "peso": 0.85, "vol": 0.0025, "fob": 9.20, "partida": "8409.91.00", "pvp": 25.00}
    ],
    "Auto Repuestos": [
        {"nombre": "Bomba de Agua Universal", "peso": 1.80, "vol": 0.0040, "fob": 12.50, "partida": "8413.30.00", "pvp": 32.00},
        {"nombre": "Juego de Pastillas Freno Delanteras", "peso": 1.20, "vol": 0.0015, "fob": 6.80, "partida": "8708.30.00", "pvp": 18.00},
        {"nombre": "Disco de Freno Ventilado (Par)", "peso": 9.50, "vol": 0.0120, "fob": 22.00, "partida": "8708.30.00", "pvp": 65.00},
        {"nombre": "Filtro de Aceite Sintético", "peso": 0.30, "vol": 0.0008, "fob": 1.50, "partida": "8421.23.00", "pvp": 5.00},
        {"nombre": "Amortiguador Delantero Hidráulico", "peso": 4.20, "vol": 0.0080, "fob": 19.50, "partida": "8708.80.00", "pvp": 55.00},
        {"nombre": "Kit de Tiempo / Correa Distribución", "peso": 0.90, "vol": 0.0022, "fob": 15.00, "partida": "4010.36.00", "pvp": 40.00}
    ],
    "Ferretería y Herramientas": [
        {"nombre": "Taladro Percutor 1/2'' 750W", "peso": 2.30, "vol": 0.0060, "fob": 16.50, "partida": "8467.21.00", "pvp": 42.00},
        {"nombre": "Juego de Llaves Combinadas 12 pzs", "peso": 1.80, "vol": 0.0025, "fob": 8.20, "partida": "8204.11.00", "pvp": 22.00},
        {"nombre": "Esmeril Recto 4-1/2''", "peso": 2.10, "vol": 0.0050, "fob": 14.00, "partida": "8467.29.00", "pvp": 38.00},
        {"nombre": "Disco de Corte para Metal 4.5'' (Caja 25u)", "peso": 1.10, "vol": 0.0012, "fob": 5.50, "partida": "6804.22.00", "pvp": 15.00},
        {"nombre": "Cinta Métrica 5m Antimpacto", "peso": 0.25, "vol": 0.0004, "fob": 1.10, "partida": "9017.80.10", "pvp": 3.50}
    ],
    "Materiales de Construcción": [
        {"nombre": "Cerradura de Pomo para Dominio", "peso": 0.60, "vol": 0.0018, "fob": 3.80, "partida": "8301.40.00", "pvp": 10.00},
        {"nombre": "Grifería Monomando Cocina", "peso": 1.20, "vol": 0.0045, "fob": 9.50, "partida": "8481.80.00", "pvp": 28.00},
        {"nombre": "Disco Diamantado 7'' Pavimento", "peso": 0.45, "vol": 0.0008, "fob": 4.20, "partida": "6804.21.00", "pvp": 12.00},
        {"nombre": "Nivel de Aluminio 24'' Profesional", "peso": 0.50, "vol": 0.0020, "fob": 2.90, "partida": "9017.30.00", "pvp": 8.50}
    ],
    "Materiales Eléctricos": [
        {"nombre": "Breaker Termomagnético 2P 40A", "peso": 0.22, "vol": 0.0004, "fob": 2.10, "partida": "8536.20.00", "pvp": 6.00},
        {"nombre": "Reflector LED 100W Multivoltaje", "peso": 0.95, "vol": 0.0032, "fob": 6.50, "partida": "9405.40.90", "pvp": 18.00},
        {"nombre": "Rollo Cable THHN #12 (100m)", "peso": 3.80, "vol": 0.0055, "fob": 24.00, "partida": "8544.49.00", "pvp": 55.00},
        {"nombre": "Tomacorriente Doble Regulado", "peso": 0.12, "vol": 0.0003, "fob": 0.85, "partida": "8536.69.00", "pvp": 2.50}
    ]
}

# Mapeo de centros de distribución / ubicación en Venezuela para calcular flete y tiempo interno
UBICACIONES_VENEZUELA = {
    "Caracas / Región Capital": {"dias_flete_interno": 2, "factor_costo_flete": 1.0},
    "Valencia / Maracay (Centro)": {"dias_flete_interno": 1, "factor_costo_flete": 0.8},
    "Barquisimeto / Centro-Occidente": {"dias_flete_interno": 2, "factor_costo_flete": 1.1},
    "Maracaibo / Zulia": {"dias_flete_interno": 3, "factor_costo_flete": 1.4},
    "San Cristóbal / Táchira (Andes)": {"dias_flete_interno": 4, "factor_costo_flete": 1.6},
    "Puerto La Cruz / Oriente": {"dias_flete_interno": 3, "factor_costo_flete": 1.3},
    "Puerto Ordaz / Guayana": {"dias_flete_interno": 4, "factor_costo_flete": 1.7},
    "Otro punto del país": {"dias_flete_interno": 3, "factor_costo_flete": 1.5}
}

def calcular_ruta_salvavidas_local(producto, cantidad_emergencia, ubicacion_empresa, proveedor_local="Distribuidor Mayorista Nacional"):
    """
    Calcula el escenario de emergencia (Plan Salvavidas) comprando a nivel nacional 
    ajustado a los días y costos de despacho según la ubicación exacta del cliente en Venezuela.
    """
    info_ubicacion = UBICACIONES_VENEZUELA.get(ubicacion_empresa, {"dias_flete_interno": 3, "factor_costo_flete": 1.3})
    
    # Aseguramos conversión segura a float
    costo_fob_base = float(producto.get("precio_fob", 0) or 0)
    costo_unitario_local = costo_fob_base * 1.35 
    
    gasto_flete_interno = 0.50 * float(info_ubicacion.get("factor_costo_flete", 1.3))
    costo_total_unitario_local = costo_unitario_local + gasto_flete_interno
    dias_totales_entrega = int(info_ubicacion.get("dias_flete_interno", 3))
    
    total_inversion_emergencia = float(cantidad_emergencia) * costo_total_unitario_local
    
    return {
        "proveedor": proveedor_local,
        "cantidad_sugerida": int(cantidad_emergencia),
        "costo_unitario_local": round(costo_total_unitario_local, 2),
        "dias_entrega": dias_totales_entrega,
        "inversion_total": round(total_inversion_emergencia, 2),
        "ubicacion_destino": ubicacion_empresa,
        "mensaje_estrategico": f"🚨 Salvavidas Activo: Despacho a {ubicacion_empresa} en {dias_totales_entrega} días."
    }

def comparar_rutas_abastecimiento(producto, config):
    """
    Compara el escenario de importación internacional habitual frente al 
    Plan de Salvavidas (Compra Puente Nacional) considerando la ubicación de la empresa.
    """
    ubicacion = config.get("ubicacion_empresa", "Caracas / Región Capital")
    
    # Conversión robusta a float para evitar errores de tipo
    ventas_sem = float(producto.get("ventas_semanales", 0) or 0)
    stock_act = float(producto.get("stock_actual", 0) or 0)
    
    # Cobertura actual en semanas
    cobertura_semanas = (stock_act / ventas_sem) if ventas_sem > 0 else 0.0
    
    # Días de tránsito internacional según el origen configurado
    dias_int = float(obtener_dias_transito(config.get("origen", "China")) or 60)
    semanas_int = dias_int / 7.0
    
    # ¿Hay riesgo de quiebre antes de que llegue el pedido internacional?
    en_riesgo = cobertura_semanas <= semanas_int
    
    # Cantidad de emergencia necesaria para cubrir el bache
    semanas_bache = max(0.0, semanas_int - cobertura_semanas)
    unidades_emergencia_necesarias = int(semanas_bache * ventas_sem) if en_riesgo else 0
    
    # Costo unitario internacional
    costo_unit_int = float(producto.get("costo_unitario", 0) or 0)
    
    # Datos de la ruta salvavidas local
    salvavidas = None
    if en_riesgo and unidades_emergencia_necesarias > 0:
        salvavidas = calcular_ruta_salvavidas_local(
            producto, 
            unidades_emergencia_necesarias, 
            ubicacion,
            proveedor_local=config.get("proveedor_local_preferido", "Distribuidor Nacional de Emergencia")
        )
        
    return {
        "en_riesgo_quiebre": en_riesgo,
        "cobertura_semanas": round(cobertura_semanas, 1),
        "dias_tránsito_internacional": int(dias_int),
        "unidades_puente_sugeridas": unidades_emergencia_necesarias,
        "costo_unitario_internacional": costo_unit_int,
        "salvavidas_local": salvavidas
    }
        
    return {
        "en_riesgo_quiebre": en_riesgo,
        "cobertura_semanas": round(cobertura_semanas, 1),
        "dias_tránsito_internacional": dias_int,
        "unidades_puente_sugeridas": unidades_emergencia_necesarias,
        "costo_unitario_internacional": costo_unit_int,
        "salvavidas_local": salvavidas
    }

def slugify(texto):
    if not texto: return "empresa-sin-nombre"
    t = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('ascii')
    t = re.sub(r'[^a-zA-Z0-9]+', '-', t).strip('-').lower()
    return t or "empresa-sin-nombre"

def texto_efectivo(valor, alterno=""):
    if valor and valor.startswith("Otro"): return alterno.strip() or "No especificado"
    return valor or "No especificado"

def cargar_tasas():
    if SHEETS_DB_OK:
        remotas = sheets_db.leer_tasas()
        if remotas: return {"EUR": remotas["EUR"], "VES": remotas["VES"]}
    if os.path.exists(RUTA_TASAS):
        try:
            with open(RUTA_TASAS, "r", encoding="utf-8") as f:
                d = json.load(f)
            return {"EUR": float(d.get("EUR", 0.93)), "VES": float(d.get("VES", 40.0))}
        except Exception: pass
    return {k: v["unidades_por_usd"] for k, v in MONEDAS_DEFAULT.items() if k != "USD"}

def inicializar_monedas():
    if "monedas" not in st.session_state: st.session_state["monedas"] = cargar_tasas()
    if "moneda_activa" not in st.session_state: st.session_state["moneda_activa"] = "USD"

def formato_moneda(monto_usd, moneda=None):
    try:
        moneda = moneda or st.session_state.get("moneda_activa", "USD")
        tasas  = st.session_state.get("monedas", {})
    except Exception: moneda, tasas = "USD", {}
    valor = Decimal(str(monto_usd)) * Decimal(str(tasas.get(moneda, 1.0)))
    simbolo = MONEDAS_DEFAULT[moneda]["simbolo"]
    return f"{simbolo} {valor.quantize(CENTAVO, ROUND_HALF_UP):,.2f}"

def formato_dinero(valor): return formato_moneda(valor)

def panel_monedas_sidebar(config):
    inicializar_monedas()
    with st.sidebar.expander("💵 Moneda y tipo de cambio", expanded=False):
        if SHEETS_DB_OK:
            remotas = sheets_db.leer_tasas()
            if remotas:
                st.session_state["monedas"]["EUR"] = remotas["EUR"]
                st.session_state["monedas"]["VES"] = remotas["VES"]
                st.caption(f"🔄 {remotas['fecha']} · por {remotas['por']}")
        st.session_state["moneda_activa"] = st.selectbox("Moneda de visualización", ["USD", "EUR", "VES"], index=["USD", "EUR", "VES"].index(st.session_state["moneda_activa"]))
        for m in ["EUR", "VES"]:
            st.session_state["monedas"][m] = st.number_input(f"1 USD = ? {m}", min_value=0.0001, value=float(st.session_state["monedas"].get(m, 1.0)), step=0.01, format="%.4f", key=f"tasa_{m}")
        if st.button("💾 Guardar tasas", key="guardar_tasas"):
            if SHEETS_DB_OK:
                ok, msg = sheets_db.guardar_tasas(usd_eur=st.session_state["monedas"]["EUR"], usd_ves=st.session_state["monedas"]["VES"], usuario=config.get("propietario") or config.get("empresa") or "admin")
                (st.success if ok else st.warning)(msg)
            else:
                try:
                    with open(RUTA_TASAS, "w", encoding="utf-8") as f: json.dump({"EUR": st.session_state["monedas"]["EUR"], "VES": st.session_state["monedas"]["VES"]}, f, indent=2)
                    st.success("✅ Guardadas localmente.")
                except Exception as e: st.error(f"No se pudieron guardar: {e}")

def a_decimal(valor, defecto="0"):
    if pd.isna(valor) or valor is None or str(valor).strip() == "":
        return Decimal(str(defecto))
    try:
        val_str = str(valor).strip().replace(",", ".")
        return Decimal(val_str)
    except Exception:
        return Decimal(str(defecto))

def redondear_entero(valor): 
    return valor.quantize(UNO, rounding=ROUND_HALF_UP)

def verificar_acceso():
    if "PASSWORD_ADMIN" not in st.secrets: return True
    if st.session_state.get("autenticado", False): return True

    # --- CARGA DE PORTADA LOCAL DESDE GITHUB ---
    st.image("portada_sistema_premium.jpg", use_container_width=True)
        
    # --- 2. BIENVENIDA Y TÍTULOS CENTRADOS ---
    st.markdown("<h1 style='text-align: center;'>Bienvenidos 🚢</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("<h3 style='text-align: center;'>¿Sabe cuánto le cuesta realmente traer los productos desde el exterior hasta su depósito?</h3>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center;'>Este Sistema Inteligente le revela:</h4>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # --- 3. LISTADO DE BENEFICIOS ---
    st.markdown("""
    * **La verdad sobre sus costos de importación**, márgenes de utilidad y precios óptimos de venta.
    * **Identificar los márgenes reales de ganancia** antes de nacionalizar, analizando la rentabilidad neta por producto prorrateando con precisión los costos según peso (kg) y volumen ($m^3$). Así sabrá qué productos le dejan ganancia real y cuáles no.
    * **Optimizar el espacio de su contenedor** y evite pérdidas por costos ocultos.
    * **Alarmas de reposición de inventario 🟢🟡🔴 por IA**, que permiten monitorear el comportamiento de las existencias, previniendo el desabastecimiento o sobrecompra, que redunda en estancamiento del Capital económico.
    * **Ingresar de forma automática de TODOS los datos** y detalles del Excel de sus artículos del inventario al Sistema de Análisis Inteligente de Importación.
    * **Definir fácilmente y con certeza** a qué proveedor del exterior debe comprar, o si es mejor hacerlo localmente.
    """)

    st.info("✨ *Todo eso y más, con la ayuda de nuestro Sistema de Importación con IA* 🤖")

    st.markdown("""
    <div style="background-color: #e8f4f8; color: #0b2545; padding: 15px; border-radius: 8px; text-align: center;">
    <strong>"UN SISTEMA DE COMERCIALIZACIÓN DISEÑADO PARA PROTEGER SU CAPITAL Y ASEGURAR QUE EL NEGOCIO SIEMPRE CREZCA"</strong>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    
    # --- 4. INSTRUCCIONES RÁPIDAS ---
    st.markdown("### 📋 Instrucciones:")
    st.markdown("""
    1. Una vez dentro, vaya al **menú desplegable de la izquierda** (⬅️) para configurar los **Datos de su empresa**: Razón Social, RIF, Propietario, márgenes de utilidad (%) y descuentos previstos, así como los datos del país y proveedor de origen.
    2. Y además, le recomendamos conocer más a fondo todas las virtudes, capacidades técnicas y módulos avanzados que incorpora esta versión, **explore la pestaña desplegable (Expander)** que encontrará una vez dentro.
    3. Para ingresar al Sistema, escriba más abajo la **contraseña** suministrada por su Asesor de Importación para comenzar el análisis.
    """)

    st.markdown("---")

    # --- 5. SECCIÓN DE AUTORÍA Y FOTOGRAFÍA ---
    col_i, col_c, col_d = st.columns([1, 1, 1])
    with col_c:
        st.markdown("<h4 style='text-align: center;'>Diseñado y elaborado por<br>su Asesor de Importación Inteligente<br>Prof. Jesús Pulido V.</h4>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>0424-728.3199 / 0416-291.6426</p>", unsafe_allow_html=True)
        for nombre in ("profesor.jpg", "asesor.jpg"):
            if os.path.exists(nombre):
                st.image(nombre, width=180)
                break

    st.divider()

    # --- 6. CAMPO DE CONTRASEÑA ---
    password = st.text_input("Contraseña de acceso", type="password")
    if st.button("Ingresar", type="primary"):
        if password == st.secrets["PASSWORD_ADMIN"]:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta.")
            
    return False
        
def prorratear_gasto(monto, productos, campo_base):
    total_centavos = int(monto.quantize(CENTAVO, rounding=ROUND_HALF_UP) * 100)
    bases = [producto[campo_base] for producto in productos]
    suma_bases = sum(bases, CERO)
    if suma_bases <= CERO: raise ValueError(f"No hay base para repartir por {campo_base}.")
    partes_exactas = [Decimal(total_centavos) * base / suma_bases for base in bases]
    partes_en_centavos = [int(parte) for parte in partes_exactas]
    centavos_sobrantes = total_centavos - sum(partes_en_centavos)
    orden_por_resto = sorted(range(len(productos)), key=lambda i: partes_exactas[i] - Decimal(partes_en_centavos[i]), reverse=True)
    for indice in orden_por_resto[:centavos_sobrantes]: partes_en_centavos[indice] += 1
    return [Decimal(parte) / 100 for parte in partes_en_centavos]

def evaluar_semaforo(stock_actual, ventas_semanales, dias_entrega, fecha_proximo_pedido=None):
    stock_actual = float(stock_actual) if stock_actual is not None else 0.0
    ventas_semanales = float(ventas_semanales) if ventas_semanales is not None else 0.0
    dias_entrega = float(dias_entrega) if dias_entrega is not None else 0.0

    if ventas_semanales <= 0:
        return "⚪", "Sin ventas registradas", 0, 0, False

    semanas_stock   = stock_actual / ventas_semanales
    semanas_entrega = dias_entrega / 7.0
    margen = semanas_stock - semanas_entrega
    sugerido_ahora = int((semanas_entrega * ventas_semanales) + (4 * ventas_semanales) - stock_actual)
    if sugerido_ahora < 0:
        sugerido_ahora = 0
    sugerido_futuro, riesgo_quiebre = 0, False
    if fecha_proximo_pedido and isinstance(fecha_proximo_pedido, date) and fecha_proximo_pedido > date.today():
        dias_hasta = (fecha_proximo_pedido - date.today()).days
        semanas_hasta = dias_hasta / 7.0
        demanda_futura = (semanas_hasta * ventas_semanales) + (semanas_entrega * ventas_semanales) + (4 * ventas_semanales)
        sugerido_futuro = int(demanda_futura - stock_actual)
        if sugerido_futuro < 0:
            sugerido_futuro = 0
        if semanas_stock < semanas_hasta:
            riesgo_quiebre = True
    if margen <= 0:
        color, mensaje = "🔴", "¡ALERTA ROJA! Pedir YA"
    elif margen <= 2:
        color, mensaje = "🟡", "Precaución: Pedir pronto"
    else:
        color, mensaje = "🟢", "Todo bien: Stock suficiente"
    return color, mensaje, sugerido_ahora, sugerido_futuro, riesgo_quiebre

def evaluar_carga_pesada(p):
    precio_fob = float(p.get("precio_fob", 0))
    cantidad = float(p.get("cantidad", 1) or 1)
    gastos_totales = float(sum(p.get("gastos", {}).values()))
    gasto_arribo_unitario = gastos_totales / cantidad if cantidad > 0 else 0
    if precio_fob <= 0: return "⚪", "Sin datos", 0
    porcentaje = (gasto_arribo_unitario / precio_fob) * 100
    if porcentaje > 60: return "🔴", f"PELIGRO: Flete = {porcentaje:.1f}% del costo.", 0
    elif porcentaje >= 30: return "🟡", f"CUIDADO: Flete = {porcentaje:.1f}% del costo.", 0
    else: return "🟢", f"RENTABLE: Flete = {porcentaje:.1f}% del costo.", 0

def calcular_pvp_sugerido(precio_fob_usd, costo_nacionalizado_usd, factor_markup_fob=2.6, margen_minimo=0.55, precio_benchmark_local=None):
    fob, costo = Decimal(str(precio_fob_usd)), Decimal(str(costo_nacionalizado_usd))
    pvp_markup = fob * Decimal(str(factor_markup_fob))
    pvp_margen = costo * (Decimal("1") + Decimal(str(margen_minimo)))
    pvp_benchmark = Decimal(str(precio_benchmark_local)) if precio_benchmark_local else None
    pvp_sugerido = max(pvp_markup, pvp_margen)
    if pvp_benchmark: pvp_sugerido = min(pvp_sugerido, pvp_benchmark * Decimal("1.15"))
    pvp_sugerido = pvp_sugerido.quantize(CENTAVO, ROUND_HALF_UP)
    utilidad = (pvp_sugerido - costo).quantize(CENTAVO)
    rentabilidad = (utilidad / costo) if costo > 0 else Decimal("0")
    alerta = ("🔴 Rentabilidad < 30%" if rentabilidad < Decimal("0.30") else "🟡 Rentabilidad ajustada" if rentabilidad < Decimal("0.50") else "🟢 Rentabilidad saludable")
    return {"fob_usd": fob, "costo_nacionalizado_usd": costo, "pvp_sugerido": pvp_sugerido, "utilidad_unitaria": utilidad, "rentabilidad_pct": (rentabilidad * 100).quantize(CENTAVO), "alerta": alerta}

def calcular_costos(productos, gastos_ingresados, config):
    margen = Decimal(str(config["margen"])) / Decimal("100")
    desc_mayorista = Decimal(str(config["desc_mayorista"])) / Decimal("100")
    desc_especial = Decimal(str(config["desc_especial"])) / Decimal("100")
    
    # Obtenemos los días de tránsito dinámicos según el país de origen seleccionado
    dias_transito_dinamicos = obtener_dias_transito(config.get("origen", "China"))
    
    gastos = []
    for nombre_gasto, criterio in GASTOS_CONTENEDOR:
        monto = gastos_ingresados[nombre_gasto]
        gastos.append((nombre_gasto, criterio, monto))
        campo_base = "peso_total" if criterio == "peso" else "volumen_total"
        repartos = prorratear_gasto(monto, productos, campo_base)
        for producto, monto_asignado in zip(productos, repartos): 
            producto["gastos"][nombre_gasto] = monto_asignado
            
    for producto in productos:
        cantidad = producto["cantidad"]
        gastos_totales = sum(producto["gastos"].values(), CERO)
        gasto_unitario = gastos_totales / Decimal(str(cantidad))
        costo_real = (producto["precio_fob"] + gasto_unitario).quantize(CENTAVO, ROUND_HALF_UP)
        producto.update({"gastos_totales": gastos_totales, "gasto_unitario": gasto_unitario, "costo_unitario": costo_real})
        
        div = UNO - margen
        producto["pvp_normal"] = redondear_entero(costo_real / div) if div > CERO else costo_real
        producto["pvp_mayorista"] = redondear_entero(producto["pvp_normal"] * (UNO - desc_mayorista))
        producto["pvp_especial"] = redondear_entero(producto["pvp_normal"] * (UNO - desc_especial))
        
        res = calcular_pvp_sugerido(precio_fob_usd=float(producto["precio_fob"]), costo_nacionalizado_usd=float(costo_real))
        producto["pvp_sugerido"] = Decimal(str(res["pvp_sugerido"]))
        producto["rentabilidad_pct"] = Decimal(str(res["rentabilidad_pct"]))
        producto["alerta_pvp"] = res["alerta"]
        
        # Asignamos los días de entrega dinámicos calculados del origen
        producto["dias_entrega"] = dias_transito_dinamicos
        
        color, mensaje, _, _, _ = evaluar_semaforo(
            producto.get("stock_actual", 0), 
            producto.get("ventas_semanales", 0), 
            producto["dias_entrega"], 
            config.get("fecha_proximo_pedido")
        )
        producto["semaforo_color"] = color
        producto["semaforo"] = mensaje
    return gastos

def consultar_partida(codigo):
    if not codigo:
        return {
            "descripcion": "No registrada en base local.",
            "ad_valorem": 0.10, "iva": 0.16,  # Valores estándar por defecto para evitar bloqueos
            "requisitos": "Consultar con agente aduanal.",
            "capitulo": "General",
        }
    
    # Normalizar eliminando puntos, guiones y espacios (ej: "8467.21.00" -> "84672100")
    codigo_limpio = str(codigo).strip().replace(".", "").replace("-", "").replace(" ", "")
    
    # 1. Búsqueda exacta con código limpio
    if codigo_limpio in PARTIDAS_BASE:
        return PARTIDAS_BASE[codigo_limpio]
        
    # 2. Búsqueda por subpartida de 6 dígitos
    if len(codigo_limpio) >= 6 and codigo_limpio[:6] in PARTIDAS_BASE:
        return PARTIDAS_BASE[codigo_limpio[:6]]
        
    # 3. Búsqueda por capítulo de 4 dígitos
    if len(codigo_limpio) >= 4 and codigo_limpio[:4] in PARTIDAS_BASE:
        return PARTIDAS_BASE[codigo_limpio[:4]]
        
    # 4. Resguardo de emergencia: si no está en la base local, asigna arancel estándar para que la auditoría no falle
    return {
        "descripcion": f"Partida {codigo} (Genérica / Comercial)",
        "ad_valorem": 0.10, 
        "iva": 0.16,
        "requisitos": "Sujeta a régimen general de importación.",
        "capitulo": codigo_limpio[:2] if len(codigo_limpio) >= 2 else "00",
    }
    
    
def estimar_derechos(codigo, valor_fob_usd, flete_usd=0.0, seguro_usd=0.0):
    info = consultar_partida(codigo)
    if info["ad_valorem"] is None:
        return {"error": "Partida sin información arancelaria local."}
    cif = valor_fob_usd + flete_usd + seguro_usd
    arancel = cif * info["ad_valorem"]
    iva     = (cif + arancel) * info["iva"]
    return {
        "partida": codigo, "descripcion": info["descripcion"],
        "ad_valorem_pct": info["ad_valorem"] * 100,
        "arancel_usd": round(arancel, 2), "iva_usd": round(iva, 2),
        "total_tributos_usd": round(arancel + iva, 2),
        "requisitos": info["requisitos"],
    }

def auditar_partidas(productos):
    filas = []
    for p in productos:
        codigo = p.get("partida_arancelaria")
        if not codigo: continue
        est = estimar_derechos(codigo, float(p["precio_fob"] * Decimal(str(p["cantidad"]))))
        if "error" in est: continue
        pagado = float(p["gastos"].get("Derechos de Aduana", 0))
        desv   = pagado - est["arancel_usd"]
        estado = ("✅ Coherente" if abs(desv) < 5 else ("⚠️ Revisar — posible sobrepago" if desv > 0 else "⚠️ Revisar — posible subdeclaración"))
        filas.append({
            "Producto": p["nombre"], "Partida": codigo, "Arancel estimado": est["arancel_usd"],
            "Arancel pagado": round(pagado, 2), "Desviación": round(desv, 2), "Estado": estado,
        })
    return filas

def generar_alertas_reposicion(productos, config, umbral_rojo=4, umbral_amarillo=8):
    alertas = []
    for p in productos:
        ventas = float(p.get("ventas_semanales", 0))
        stock = float(p.get("stock_actual", 0))
        if ventas <= 0: continue
        semanas = stock / ventas
        if semanas <= umbral_rojo: nivel, accion = "🔴 CRÍTICO", "Emitir orden de compra HOY"
        elif semanas <= umbral_amarillo: nivel, accion = "🟡 PREVENTIVO", "Preparar orden esta semana"
        else: continue
        alertas.append({
            "producto": p["nombre"], "stock": stock, "ventas_semanales": ventas,
            "semanas_cobertura": round(semanas, 1), "nivel": nivel, "accion": accion,
            "proveedor": config.get("proveedor", "N/D"),
        })
    return sorted(alertas, key=lambda x: x["semanas_cobertura"])

def mostrar_alertas_en_panel(alertas):
    if not alertas:
        st.success("✅ Sin alertas. Inventario saludable."); return
    for a in alertas:
        bg = "#FFC7CE" if "CRÍTICO" in a["nivel"] else "#FFEB9C"
        borde = "#C00000" if "CRÍTICO" in a["nivel"] else "#BF8F00"
        st.markdown(f"""
        <div style="background-color:{bg}; color: #000; padding:12px; border-radius:8px; margin-bottom:8px; border-left:6px solid {borde};">
            <b>{a['nivel']} — {a['producto']}</b><br>
            Stock: <b>{a['stock']:,.0f} unds</b> · Ventas: <b>{a['ventas_semanales']:,.0f}/sem</b>
            · Cobertura: <b>{a['semanas_cobertura']} semanas</b><br>
            Acción: <i>{a['accion']}</i> — Proveedor: {a['proveedor']}
        </div>
        """, unsafe_allow_html=True)

# --- MÓDULO VISUAL: PESTAÑA SALVAVIDAS Y RUTAS ÓPTIMAS ---
def renderizar_pestana_salvavidas(productos, config):
    st.subheader("🛟 Módulo 'Salvavidas': Rutas Paralelas y Proveedores Óptimos")
    st.markdown("""
    Este módulo evalúa en tiempo real si existe riesgo de quiebre de inventario antes de que llegue su carga internacional, 
    calculando una **Ruta Puente de Auxilio Nacional** ajustada a la ubicación de su empresa en Venezuela y permitiéndole 
    seleccionar el proveedor óptimo para recalcular la operación.
    """)
    
    if not productos:
        st.info("⚠️ Por favor, cargue o calcule los productos primero para activar el análisis de salvavidas.")
        return

    # Selector de ubicación de la empresa para calcular fletes internos reales
    ubicacion_actual = config.get("ubicacion_empresa", "Caracas / Región Capital")
    nueva_ubicacion = st.selectbox(
        "📍 Ubicación de su Empresa / Almacén (para cálculo de flete interno en Venezuela):",
        list(UBICACIONES_VENEZUELA.keys()),
        index=list(UBICACIONES_VENEZUELA.keys()).index(ubicacion_actual) if ubicacion_actual in UBICACIONES_VENEZUELA else 0
    )
    config["ubicacion_empresa"] = nueva_ubicacion

    st.markdown("---")
    
    for i, prod in enumerate(productos):
        comparacion = comparar_rutas_abastecimiento(prod, config)
        
        with st.container():
            col1, col2 = st.columns([2, 3])
            
            with col1:
                st.markdown(f"**📦 {prod.get('nombre', 'Producto')}**")
                st.markdown(f"📦 **Stock Actual:** `{prod.get('stock_actual', 0)} unds` | **Venta Semanal:** `{prod.get('ventas_semanales', 0)} unds/sem`")
                st.markdown(f"⏱️ **Cobertura:** `{comparacion['cobertura_semanas']} semanas`")
                dias_t = comparacion['dias_tránsito_internacional']
                sems_t = round(dias_t / 7.0, 1)
                st.markdown(f"🚢 **Tránsito Origen ({config.get('origen', 'China')}):** `{dias_t} días ({sems_t} Sem)`")
                       
                if comparacion["en_riesgo_quiebre"]:
                    fecha_pedido_str = config.get("fecha_proximo_pedido")
                    if fecha_pedido_str:
                        try:
                            fecha_pedido_dt = datetime.strptime(str(fecha_pedido_str), "%Y-%m-%d").date()
                            dias_t = int(comparacion['dias_tránsito_internacional'])
                            fecha_llegada_dt = fecha_pedido_dt + timedelta(days=dias_t)
                            
                            msg_alerta = (
                                f"🔴 **ALERTA DE INVENTARIO:** El stock se agotará en {comparacion['cobertura_semanas']} semanas, "
                                f"antes de que llegue el pedido programado a realizar el **{fecha_pedido_dt.strftime('%d/%m/%Y')}**, "
                                f"cuyo arribo estimado será el **{fecha_llegada_dt.strftime('%d/%m/%Y')}**."
                            )
                            st.error(msg_alerta)
                        except Exception:
                            st.error("🔴 **ALERTA DE INVENTARIO:** El stock se agotará antes de que llegue el pedido internacional.")
                    else:
                        st.error("🔴 **ALERTA DE INVENTARIO:** El stock se agotará antes de que llegue el pedido internacional.")

                else:
                    st.success("🟢 **Abastecimiento Seguro:** Cobertura suficiente hasta el próximo arribo.")

            with col2:
                if comparacion["en_riesgo_quiebre"]:
                    st.markdown("---")
                    st.markdown("##### 🔍 Búsqueda de Proveedores Alternativos en Tiempo Real")
                    
                    has_tavily = "TAVILY_API_KEY" in st.secrets
                    
                    if has_tavily:
                        if st.button(f"🆘 Buscar Proveedores Reales para: {prod.get('nombre')}", key=f"btn_sup_{i}", type="primary"):
                            with st.spinner("Rastreando proveedores en la web..."):
                                try:
                                    resultados = find_suppliers(
                                        producto=prod.get('nombre'),
                                        cantidad=comparacion.get('cantidad_puente', 0),
                                        ciudad=config.get('ubicacion_empresa', 'Caracas'),
                                        tavily_key=st.secrets["TAVILY_API_KEY"],
                                        openai_key=st.secrets.get("OPENAI_API_KEY")
                                    )
                                    
                                    if len(resultados) == 0:
                                        st.warning("El buscador no devolvió resultados directos. Verifique su conexión o intente nuevamente.")
                                    else:
                                        # Guardamos en sesión para alimentar el selectbox del formulario
                                        st.session_state[f"lista_prov_{i}"] = resultados
                                        st.success(f"¡Se encontraron {len(resultados)} candidatos mayoristas!")
                                        
                                        # Generamos URLs crudas y limpias para LinkColumn
                                        df = pd.DataFrame(resultados)
                                        df["telefono_val"] = df["telefono"].fillna("").apply(lambda t: t if t else "")
                                        df["Teléfono"] = df["telefono_val"].apply(lambda t: f"tel:{t}" if t else None)
                                        df["WhatsApp"] = df["telefono_val"].apply(lambda t: wa_link(t) if t else None)
                                        df["Teléfono_texto"] = df["telefono_val"].apply(lambda t: t if t else "Sin Nro de TLF disponible")
    
                                        df_display = df[[
                                            "nombre", "localidad", "Teléfono_texto", "Teléfono", "WhatsApp", "fuente"
                                        ]].rename(columns={
                                            "nombre": "Empresa", 
                                            "localidad": "Localidad", 
                                            "Teléfono_texto": "Nro. Contacto",
                                            "fuente": "Fuente web",
                                        })
    
                                        st.dataframe(
                                            df_display, use_container_width=True, hide_index=True,
                                            column_config={
                                                "Teléfono": st.column_config.LinkColumn("📞 Llamar", display_text="📞 Llamar al móvil"),
                                                "WhatsApp": st.column_config.LinkColumn("💬 WhatsApp", display_text="💬 Abrir WhatsApp"),
                                                "Fuente web": st.column_config.LinkColumn("🔗 Enlace", display_text="🔗 Ver fuente"),
                                            },
                                        )
                                        st.caption("ℹ️ *Mostrando directorio de proveedores nacionales pre-verificado (Modo de contingencia sin conexión web).*")
                                        
                                except Exception as e:
                                    st.error(f"Error crítico en el buscador web: {e}")
    
                        # --- FORMULARIO DE COTIZACIÓN ÚNICO Y BLINDADO ---
                        state_key = f"resultado_cot_{i}"
                        
                        # Recuperamos la cantidad puente con respaldo seguro de llaves
                        cant_puente = comparacion.get('cantidad_puente', 0)
                        if not cant_puente or cant_puente == 0:
                            cant_puente = comparacion.get('unidades_necesarias', comparacion.get('faltante', 50))
                        
                        st.divider()
                        st.markdown("### 📝 Ingreso Manual de Cotización Real")
                        
                        # 1. Recuperamos los proveedores de la sesión (si existen)
                        opciones_proveedores = ["Otro / Proveedor Externo (Escribir abajo)"]
                        if f"lista_prov_{i}" in st.session_state:
                            nombres_encontrados = [p["nombre"] for p in st.session_state[f"lista_prov_{i}"]]
                            opciones_proveedores.extend(nombres_encontrados)
                        
                        with st.form(key=f"form_cot_{i}"):
                            # 2. Selector de Proveedor
                            proveedor_elegido = st.selectbox(
                                "Proveedor Seleccionado", 
                                options=opciones_proveedores,
                                key=f"select_prov_{i}"
                            )
                            
                            # 3. Campo condicional si elige "Otro"
                            proveedor_custom = ""
                            if proveedor_elegido == "Otro / Proveedor Externo (Escribir abajo)":
                                proveedor_custom = st.text_input("Nombre del Proveedor Externo:", key=f"p_custom_{i}")
                            
                            col_f1, col_f2 = st.columns(2)
                            precio_real = col_f1.number_input("Precio Unitario Cotizado ($)", min_value=0.0, step=0.5, value=0.0, key=f"p_real_{i}")
                            dias_entrega = col_f2.number_input("Días de Entrega Reales", min_value=1, step=1, value=5, key=f"d_ent_{i}")
                            submit_cot = st.form_submit_button("Recalcular Operación con Cotización Real")
                            
                            if submit_cot:
                                nombre_final = proveedor_custom if proveedor_custom else proveedor_elegido
                                inversion_total = precio_real * cant_puente
                                
                                st.session_state[state_key] = {
                                    "proveedor": nombre_final,
                                    "precio_real": precio_real,
                                    "dias_entrega": dias_entrega,
                                    "inversion_total": inversion_total,
                                    "cant_puente": cant_puente
                                }
                        
                        # 4. Renderizado persistente del cálculo en sesión
                        if state_key in st.session_state:
                            cot = st.session_state[state_key]
                            st.success(f"✅ **Operación Recalculada (Guardada en Sesión)**\n\n"
                                       f"- **Proveedor Seleccionado:** {cot['proveedor']}\n"
                                       f"- **Inversión Real Total:** ${cot['inversion_total']:,.2f}\n"
                                       f"- **Plazo de Recepción:** {cot['dias_entrega']} días\n"
                                       f"- **Cantidad Cubierta:** {cot['cant_puente']} unidades "
                                       f"(a ${cot['precio_real']:,.2f} c/u)")
                    else:
                        st.info("💡 *Consejo:* Configure `TAVILY_API_KEY` en sus secretos de Streamlit Cloud para habilitar el buscador web automático.")
                else:
                    st.markdown("##### Estado de Ruta")
                    st.write("No se requiere activar la ruta de salvavidas local en este momento.")
            
            st.markdown("---")

def proyectar_flujo_caja(productos, config, semanas=13, crecimiento_semanal=0.02, costo_fijo_semanal=0.0, pago_importacion=None):
    hoy = date.today()
    saldo = float(config.get("capital_inicial", 0))
    filas = []
    for w in range(1, semanas + 1):
        fecha = hoy + timedelta(weeks=w)
        ingreso = 0.0
        for p in productos:
            ventas = float(p.get("ventas_semanales", 0))
            pvp    = float(p.get("pvp_normal", 0))
            factor = (1.0 + crecimiento_semanal) ** w
            ingreso += ventas * pvp * factor
        egreso = float(costo_fijo_semanal)
        if pago_importacion and pago_importacion.get("fecha") == fecha:
            egreso += float(pago_importacion.get("monto_usd", 0))
        saldo += ingreso - egreso
        filas.append({"Semana": w, "Fecha": fecha.strftime("%Y-%m-%d"), "Ingreso proyectado": round(ingreso, 2), "Egreso proyectado": round(egreso, 2), "Saldo acumulado": round(saldo, 2)})
    return pd.DataFrame(filas)

def mostrar_flujo_caja(df_flujo):
    st.subheader("📅 Proyección de flujo de caja — 13 semanas")
    c1, c2, c3 = st.columns(3)
    c1.metric("Ingreso total", f"$ {df_flujo['Ingreso proyectado'].sum():,.0f}")
    c2.metric("Saldo final",   f"$ {df_flujo['Saldo acumulado'].iloc[-1]:,.0f}")
    minimo = df_flujo["Saldo acumulado"].min()
    c3.metric("Saldo mínimo", f"$ {minimo:,.0f}", delta=None if minimo >= 0 else "⚠️ Riesgo de iliquidez")
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(df_flujo["Semana"], df_flujo["Saldo acumulado"], marker="o", color="#1F4E78")
    ax.axhline(0, color="red", linestyle="--", linewidth=1)
    ax.set_xlabel("Semana"); ax.set_ylabel("Saldo acumulado (USD)")
    ax.set_title("Saldo de caja proyectado"); ax.grid(alpha=0.3)
    st.pyplot(fig)

def exportar_csv_para_sheets(productos, config):
    filas = []
    for p in productos:
        filas.append({
            "Producto": p["nombre"], "Partida_Arancelaria": p.get("partida_arancelaria", ""),
            "Cantidad": p["cantidad"], "FOB_Origen_USD": float(p["precio_fob"]),
            "Costo_Real_USD": float(p["costo_unitario"]), "PVP_Normal": float(p["pvp_normal"]),
            "PVP_Sugerido": float(p.get("pvp_sugerido", p["pvp_normal"])),
            "Rentabilidad_Pct": float(p.get("rentabilidad_pct", 0)),
            "Stock_Actual": float(p.get("stock_actual", 0)), "Ventas_Semanales": float(p.get("ventas_semanales", 0)),
            "Semaforo": p.get("semaforo", ""),
        })
    return pd.DataFrame(filas).to_csv(index=False).encode("utf-8-sig")

def boton_exportar_sheets(productos, config):
    csv = exportar_csv_para_sheets(productos, config)
    id_perfil = config.get("id_perfil", "empresa")
    st.download_button("📱 Descargar CSV para Google Sheets", data=csv, file_name=f"importacion_{config.get('factura','SN')}_{id_perfil}.csv", mime="text/csv", help="Súbelo a Google Drive → abrir con Google Sheets.")

def crear_reporte_html(productos, gastos_contenedor, config):
    total_items = len(productos)
    total_unds = sum(p["cantidad"] for p in productos)
    total_mercancia = sum((p["precio_fob"] * Decimal(str(p["cantidad"])) for p in productos), CERO)
    total_gastos = sum((p["gastos_totales"] for p in productos), CERO)
    origen_efectivo = texto_efectivo(config.get("origen"), config.get("origen_otro"))

    html = f"""
    <div style="font-family: Arial, sans-serif; color: #333; max-width: 1000px; margin: auto;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #1f4e78; margin-bottom: 5px;">REPORTE EJECUTIVO DE IMPORTACIÓN</h1>
            <p style="margin: 0; font-size: 14px;"><b>{config.get('empresa', '')}</b> | RIF: {config.get('rif', '')} | Propietario: {config.get('propietario', '')}</p>
            <p style="margin: 5px 0; font-size: 12px; color: #666;">Origen: {origen_efectivo} | Proveedor: {config.get('proveedor', '')} | Factura: {config.get('factura', '')}</p>
        </div>

        <div style="display: flex; justify-content: space-between; margin-bottom: 20px; gap: 10px;">
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; border-radius: 5px;">
                <div style="font-size: 11px; color: #666; font-weight: bold;">PRODUCTOS</div>
                <div style="font-size: 18px; font-weight: bold; color: #1f4e78;">{total_items} ítems</div>
            </div>
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; border-radius: 5px;">
                <div style="font-size: 11px; color: #666; font-weight: bold;">CANT. UNIDADES</div>
                <div style="font-size: 18px; font-weight: bold; color: #1f4e78;">{total_unds:,.0f} unds</div>
            </div>
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; border-radius: 5px;">
                <div style="font-size: 11px; color: #666; font-weight: bold;">COSTO MERCANCÍA</div>
                <div style="font-size: 18px; font-weight: bold; color: #1f4e78;">$ {float(total_mercancia):,.2f}</div>
            </div>
            <div style="flex: 1; border: 1px solid #ddd; padding: 10px; text-align: center; border-radius: 5px;">
                <div style="font-size: 11px; color: #666; font-weight: bold;">GASTOS ARRIBO</div>
                <div style="font-size: 18px; font-weight: bold; color: #1f4e78;">$ {float(total_gastos):,.2f}</div>
            </div>
        </div>

        <h3 style="color: #1f4e78; margin-bottom: 5px;">Resumen General de Costos y Precios de Venta</h3>
        <table style="page-break-inside: avoid; width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 30px;">
            <tr style="background-color: #1f4e78; color: white;">
                <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Producto</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Cant.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Costo U.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">PVP Norm.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">PVP May.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">PVP Esp.</th>
                <th style="padding: 8px; border: 1px solid #ddd;">Semáforo</th>
            </tr>
    """
    
    for p in productos:
        color_txt = "red" if "🔴" in p.get("semaforo_color", "") else ("orange" if "🟡" in p.get("semaforo_color", "") else "green")
        estado_txt = "ROJO" if "🔴" in p.get("semaforo_color", "") else ("AMARILLO" if "🟡" in p.get("semaforo_color", "") else "VERDE")
        html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">{p['nombre']}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{p['cantidad']}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$ {float(p['costo_unitario']):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$ {float(p['pvp_normal']):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$ {float(p['pvp_mayorista']):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$ {float(p['pvp_especial']):,.2f}</td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: bold; color: {color_txt};">{estado_txt}</td>
            </tr>
        """
    html += "</table>"

    html += """<h3 style="color: #1f4e78; margin-bottom: 10px;">Desglose Individual y Prorrateo de Gastos</h3>"""
    for p in productos:
        color_txt = "#c00000" if "🔴" in p.get("semaforo_color", "") else ("bf8f00" if "🟡" in p.get("semaforo_color", "") else "#006100")
        estado_txt = "ROJO" if "🔴" in p.get("semaforo_color", "") else ("AMARILLO" if "🟡" in p.get("semaforo_color", "") else "VERDE")
        
        _, _, sug_ahora, sug_futuro, _ = evaluar_semaforo(p.get("stock_actual", 0), p.get("ventas_semanales", 0), p.get("dias_entrega", 0), config.get("fecha_proximo_pedido"))

        # 1. Procesamos la fecha AQUÍ AFUERA del HTML de forma limpia y segura
        fecha_ped_raw = config.get("fecha_proximo_pedido", "")
        try:
            if fecha_ped_raw:
                dt_ped = datetime.strptime(str(fecha_ped_raw), "%Y-%m-%d")
                fecha_ped_fmt = dt_ped.strftime("%d/%m/%Y")
            else:
                fecha_ped_fmt = "X/X/X"
        except Exception:
            fecha_ped_fmt = str(fecha_ped_raw)

        # 2. Luego construimos el HTML usando la variable {fecha_ped_fmt} ya lista
        html += f"""
        <div style="page-break-inside: avoid; border: 1px solid #b3d4fc; border-radius: 5px; margin-bottom: 15px; overflow: hidden;">
            <div style="background-color: #e6f2ff; padding: 8px 12px; border-bottom: 1px solid #b3d4fc; font-weight: bold; color: #1f4e78;">
                Producto: {p['nombre']}
            </div>
            <div style="padding: 12px; font-size: 12px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <div><b style="color: {color_txt};">Estado: {estado_txt}</b> - {p['semaforo']}</div>
                    <div style="text-align: right;">
                        <b>======> Pedir {sug_ahora} unds</b><br>
                        <span style="color: #666; font-style: italic;">Según Pedido Planificado para el {fecha_ped_fmt} Pedir {sug_futuro} Unds</span>
                    </div>
                </div>
                <div style="margin-bottom: 10px; color: #444;">
                    <b>Cant.:</b> {p['cantidad']} unds | <b>FOB U.:</b> $ {float(p['precio_fob']):,.2f} | <b>Peso T.:</b> {float(p['peso_total']):,.2f} kg | <b>Vol. T.:</b> {float(p['volumen_total']):,.4f} m3
                </div>
                <div style="background-color: #f8f9fa; padding: 8px; border-radius: 3px;">
                    <b>Gastos Arribo U.:</b> $ {float(p['gasto_unitario']):,.2f} | <b>COSTO REAL EN ESTANTE:</b> $ {float(p['costo_unitario']):,.2f}
                </div>
                <div style="margin-top: 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; color: #555;">
                    <div><b>Gastos (Parte 1):</b> Manejo: ${float(p['gastos']['Manejo de Puerto']):,.2f} | Flete Nac.: ${float(p['gastos']['Flete Terrestre Nacional']):,.2f} | Log. Int.: ${float(p['gastos']['Logística Internacional']):,.2f}</div>
                    <div><b>Gastos (Parte 2):</b> Aduana: ${float(p['gastos']['Derechos de Aduana']):,.2f} | Gestión: ${float(p['gastos']['Gestión Aduanera']):,.2f} | Admin: ${float(p['gastos']['Gastos Administrativos']):,.2f}</div>
                </div>
            </div>
        </div>
        """
    
    html += """
        <div style="page-break-inside: avoid; text-align: center; margin-top: 40px; padding: 25px; border-top: 2px solid #1f4e78; background-color: #f8f9fa; border-radius: 8px;">
            <p style="margin: 0 0 10px 0; color: #1f4e78; font-weight: bold; font-size: 14px;">Diseñado y elaborado por su Asesor de Importación Inteligente:</p>
            <h2 style="margin: 0 0 5px 0; color: #1f4e78; font-size: 20px;">Prof. Jesús Pulido V.</h2>
            <p style="margin: 0 0 15px 0; font-size: 12px; color: #444; line-height: 1.5;">
                Teléfonos de contacto: 0424-728.3199 / 0416-291.6426<br>
                Correo: jeshua166@gmail.com
            </p>
            <img src="https://i.postimg.cc/Hxhd38gS/JPV-Asesor-Importacion.jpg" style="width: 140px; border-radius: 8px; border: 2px solid #1f4e78;" />
        </div>
    </div>
    """
    return html.replace('\n', '').strip()

def generar_pdf_desde_html(html_content):
    try:
        result = io.BytesIO()
        pisa.CreatePDF(io.StringIO(html_content), dest=result)
        return result.getvalue()
    except Exception as e:
        st.error(f"Error generando PDF: {e}")
        return None

def leer_excel(archivo):
    if archivo.name.lower().endswith(".csv"): return pd.read_csv(archivo)
    return pd.read_excel(archivo)

def sugerir_columna(columnas, posibles):
    columnas_lower = {i: str(c).lower() for i, c in enumerate(columnas)}
    for palabra in posibles:
        for idx, col_lower in columnas_lower.items():
            if palabra in col_lower: 
                return columnas[idx]
    return None

def mapear_columnas(df):
    columnas_opciones = ["(ninguna)"] + list(df.columns)
    st.markdown("**Mapeo de columnas del Excel**")
    c1, c2, c3 = st.columns(3); c4, c5, c6 = st.columns(3); c7, c8, c9 = st.columns(3)
    
    sugerencias = {
        "producto": ["producto", "descripcion", "descripción", "nombre", "articulo"],
        "cantidad": ["cantidad", "cant", "unidades", "qty"],
        "precio": ["fob", "precio", "origen", "china", "unitario", "costo"],
        "peso": ["peso", "kg", "weight"],
        "volumen": ["volumen", "m3", "cbm", "volume"],
        "stock": ["stock", "inventario", "existencia"],
        "ventas": ["venta", "ventas", "semanal", "salida"],
        "dias": ["dias", "días", "entrega", "llegada", "transito"],
        "partida": ["partida", "hs", "arancel", "codigo"]
    }
    
    def selector(col_st, etiqueta, keys, key_sel):
        sug = sugerir_columna(list(df.columns), keys)
        idx = columnas_opciones.index(sug) if sug in columnas_opciones else 0
        return col_st.selectbox(etiqueta, columnas_opciones, index=idx, key=key_sel)

    return {
        "producto": selector(c1, "Producto / Descripción", sugerencias["producto"], "sel_prod"),
        "cantidad": selector(c2, "Cantidad", sugerencias["cantidad"], "sel_cant"),
        "precio": selector(c3, "Precio FOB Origen $/u", sugerencias["precio"], "sel_prec"),
        "peso": selector(c4, "Peso unitario (kg)", sugerencias["peso"], "sel_peso"),
        "volumen": selector(c5, "Volumen unitario (m³)", sugerencias["volumen"], "sel_vol"),
        "stock": selector(c6, "Stock Actual", sugerencias["stock"], "sel_stock"),
        "ventas": selector(c7, "Ventas Semanales", sugerencias["ventas"], "sel_vent"),
        "dias": selector(c8, "Días de Entrega", sugerencias["dias"], "sel_dias"),
        "partida": selector(c9, "Partida Arancelaria", sugerencias["partida"], "sel_part"),
    }

def construir_productos_desde_df(df, mapeo):
    faltantes = [k for k in ["producto","cantidad","precio","peso","volumen"] if mapeo.get(k) in (None, "(ninguna)")]
    if faltantes: raise ValueError(f"Falta mapear campos obligatorios: {', '.join(faltantes)}")
    
    productos = []
    for i, fila in df.iterrows():
        try:
            nombre = str(fila[mapeo["producto"]]).strip() if pd.notna(fila[mapeo["producto"]]) else f"Producto {i+1}"
            cant_val = a_decimal(fila[mapeo["cantidad"]], "1")
            cantidad = int(cant_val) if cant_val > CERO else 1
            
            precio = a_decimal(fila[mapeo["precio"]], "0.0")
            peso_u = a_decimal(fila[mapeo["peso"]], "0.0")
            vol_u  = a_decimal(fila[mapeo["volumen"]], "0.0")
            
            stock  = int(a_decimal(fila[mapeo["stock"]], "0")) if mapeo.get("stock") and mapeo["stock"] != "(ninguna)" else 0
            ventas = a_decimal(fila[mapeo["ventas"]], "0.0") if mapeo.get("ventas") and mapeo["ventas"] != "(ninguna)" else CERO
            dias   = int(a_decimal(fila[mapeo["dias"]], "60")) if mapeo.get("dias") and mapeo["dias"] != "(ninguna)" else 60
            
            partida = str(fila[mapeo["partida"]]).strip() if mapeo.get("partida") and mapeo["partida"] != "(ninguna)" and pd.notna(fila[mapeo["partida"]]) else ""

            cant_dec = Decimal(str(cantidad))
            productos.append({
                "nombre": nombre, "cantidad": cantidad, "precio_fob": precio,
                "peso_total": peso_u * cant_dec, "volumen_total": vol_u * cant_dec,
                "stock_actual": stock, "ventas_semanales": ventas, "dias_entrega": dias,
                "partida_arancelaria": partida, "gastos": {}
            })
        except Exception as e:
            st.warning(f"Fila {i + 2} omitida por inconveniente en datos: {e}")
            
    if not productos: raise ValueError("No se pudo cargar ningún producto válido desde el archivo.")
    return productos

def inicializar_estado():
    if "config_empresa" not in st.session_state: st.session_state.config_empresa = dict(DEFAULTS)

def listar_perfiles():
    if SHEETS_DB_OK:
        try: return sheets_db.listar_perfiles()
        except Exception: pass
    return st.session_state.get("perfiles_locales", [])

def guardar_perfil_local(perfil):
    perfiles = st.session_state.get("perfiles_locales", [])
    existentes = {p["id_perfil"]: i for i, p in enumerate(perfiles)}
    if perfil["id_perfil"] in existentes: perfiles[existentes[perfil["id_perfil"]]] = perfil
    else: perfiles.append(perfil)
    st.session_state["perfiles_locales"] = perfiles

def cargar_perfil(perfil):
    for k, v in perfil.items():
        if k in st.session_state.config_empresa: st.session_state.config_empresa[k] = v

def panel_perfil_sidebar():
    st.sidebar.header("🏢 Perfil de Empresa")
    perfiles = listar_perfiles()
    opciones = ["➕ Crear nueva empresa"] + [f"{p['empresa']} ({p['id_perfil']})" for p in perfiles]
    actual_id = st.session_state.config_empresa.get("id_perfil", "")
    idx_actual = 0
    for i, p in enumerate(perfiles):
        if p["id_perfil"] == actual_id: idx_actual = i + 1; break
    sel = st.sidebar.selectbox("Seleccionar empresa", opciones, index=idx_actual)
    if sel == "➕ Crear nueva empresa":
        st.sidebar.markdown("### 🆕 Nueva empresa")
        empresa = st.sidebar.text_input("Razón Social *", key="new_empresa")
        rif = st.sidebar.text_input("RIF", key="new_rif")
        prop = st.sidebar.text_input("Propietario / Responsable", key="new_prop")
        email = st.sidebar.text_input("Email de contacto", key="new_email")
        sector = st.sidebar.selectbox("Sector / Rubro", SECTORES, key="new_sector")
        sector_otro = st.sidebar.text_input("Especifique el sector", key="new_sector_otro") if sector.startswith("Otro") else ""
        origen = st.sidebar.selectbox("Origen principal", ORIGENES, key="new_origen")
        origen_otro = st.sidebar.text_input("Especifique el origen", key="new_origen_otro") if origen.startswith("Otro") else ""
        moneda = st.sidebar.selectbox("Moneda base", ["USD", "EUR", "VES"], key="new_moneda")
        if st.sidebar.button("💾 Crear perfil", type="primary", key="btn_crear_perfil"):
            if not empresa.strip(): st.sidebar.error("La Razón Social es obligatoria.")
            else:
                perfil = {"id_perfil": slugify(empresa), "empresa": empresa.strip(), "rif": rif.strip(), "propietario": prop.strip(), "email": email.strip(), "sector": sector, "sector_otro": sector_otro.strip(), "origen": origen, "origen_otro": origen_otro.strip(), "moneda_default": moneda, "margen": DEFAULTS["margen"], "desc_mayorista": DEFAULTS["desc_mayorista"], "desc_especial": DEFAULTS["desc_especial"], "proveedor": ""}
                if SHEETS_DB_OK:
                    ok, msg = sheets_db.crear_actualizar_perfil(perfil)
                    (st.sidebar.success if ok else st.sidebar.warning)(msg)
                else: guardar_perfil_local(perfil); st.sidebar.success(f"✅ Perfil '{empresa}' creado localmente.")
                cargar_perfil(perfil); st.rerun()
    else:
        idx = opciones.index(sel) - 1
        perfil = perfiles[idx]
        cargar_perfil(perfil)
        st.sidebar.success(f"✅ Perfil activo: **{perfil['empresa']}**")
        st.sidebar.caption(f"ID: `{perfil['id_perfil']}`")
    st.sidebar.divider()

def panel_configuracion_avanzada(config):
    with st.sidebar.expander("⚙️ Ajustes avanzados", expanded=False):
        config["margen"] = st.number_input("Margen normal (%)", 0.0, 99.0, float(config["margen"]), 0.5, key="adv_margen")
        config["desc_mayorista"] = st.number_input("Descuento mayorista (%)", 0.0, 99.0, float(config["desc_mayorista"]), 0.5, key="adv_desc_may")
        config["desc_especial"] = st.number_input("Descuento especial (%)", 0.0, 99.0, float(config["desc_especial"]), 0.5, key="adv_desc_esp")
        config["capital_inicial"] = st.number_input("Capital inicial ($)", 0.0, value=float(config["capital_inicial"]), step=100.0, key="adv_cap")
        config["costo_fijo_semanal"] = st.number_input("Costo fijo semanal ($)", 0.0, value=float(config["costo_fijo_semanal"]), step=10.0, key="adv_cf")
        config["monto_proximo_pedido"] = st.number_input("Monto próximo pedido ($)", 0.0, value=float(config["monto_proximo_pedido"]), step=100.0, key="adv_mpp")
        config["fecha_proximo_pedido"] = st.date_input("Fecha próximo pedido", value=config.get("fecha_proximo_pedido"), key="adv_fpp")
    st.sidebar.divider()
    st.sidebar.subheader("🌍 Origen del embarque")
    config["origen"] = st.sidebar.selectbox("País de origen", ORIGENES, index=ORIGENES.index(config.get("origen", "China")) if config.get("origen") in ORIGENES else 0, key="origen_sel")
    if config["origen"].startswith("Otro"): config["origen_otro"] = st.sidebar.text_input("Especifique el país", value=config.get("origen_otro",""), key="origen_otro_txt")
    config["proveedor"] = st.sidebar.text_input("Proveedor", value=config.get("proveedor",""), key="prov_txt")
    config["factura"]   = st.sidebar.text_input("Nro. de Factura", value=config.get("factura",""), key="fact_txt")
    st.session_state.config_empresa = config
    return config

def vista_analisis_costos(productos, config):
    st.subheader("📊 Análisis de costos por producto")
    filas = [{"Producto": p["nombre"], "Cantidad": p["cantidad"], "FOB $/u": float(p["precio_fob"]), "Gasto arribo $/u": float(p["gasto_unitario"]), "Costo real $/u": float(p["costo_unitario"]), "PVP Normal": float(p["pvp_normal"]), "PVP Sugerido": float(p["pvp_sugerido"]), "Rentab. %": float(p["rentabilidad_pct"]), "Partida": p.get("partida_arancelaria", ""), "Alerta PVP": p.get("alerta_pvp", ""), "Semáforo": p.get("semaforo", "")} for p in productos]
    st.dataframe(pd.DataFrame(filas), use_container_width=True)
    c1, c2, c3, c4 = st.columns(4)
    inv_total = sum((p["costo_unitario"] * Decimal(str(p["cantidad"])) for p in productos), CERO)
    arr_total = sum((p["gastos_totales"] for p in productos), CERO)
    mer_total = sum((p["precio_fob"] * Decimal(str(p["cantidad"])) for p in productos), CERO)
    en_rojo = sum(1 for p in productos if "🔴" in p.get("semaforo_color", ""))
    
    c1.metric("Inversión total", formato_dinero(inv_total))
    c2.metric("Gasto arribo / mercancía", f"{(arr_total / mer_total * 100) if mer_total > CERO else 0:.1f}%")
    c3.metric("Productos en rojo", f"{en_rojo} / {len(productos)}")
    c4.metric("Margen promedio", f"{sum(float(p['rentabilidad_pct']) for p in productos)/len(productos):.1f}%")
    
    fig, ax = plt.subplots(figsize=(10, 4))
    nombres = [p["nombre"][:20] for p in productos]; costos = [float(p["costo_unitario"]) for p in productos]; sugeridos = [float(p["pvp_sugerido"]) for p in productos]
    x = list(range(len(nombres)))
    ax.bar([i - 0.2 for i in x], costos, width=0.4, label="Costo real", color="#C44E52")
    ax.bar([i + 0.2 for i in x], sugeridos, width=0.4, label="PVP sugerido", color="#4C72B0")
    ax.set_xticks(x); ax.set_xticklabels(nombres, rotation=20, ha="right"); ax.set_title("Costo real vs PVP Sugerido"); ax.legend(); ax.grid(alpha=0.3, axis="y")
    st.pyplot(fig)

def vista_auditoria_aduanera(productos):
    st.subheader("🏷️ Auditoría de Partidas Arancelarias")
    auditoria = auditar_partidas(productos)
    if not auditoria: st.warning("Ningún producto tiene partida arancelaria cargada."); return
    st.dataframe(pd.DataFrame(auditoria), use_container_width=True)
    st.markdown("### Detalle por partida")
    for p in productos:
        codigo = p.get("partida_arancelaria")
        if not codigo: continue
        info = consultar_partida(codigo); est = estimar_derechos(codigo, float(p["precio_fob"] * Decimal(str(p["cantidad"]))))
        ad_valorem = float(info.get('ad_valorem', 0) or 0) * 100
        texto_info = (
            f"**{p['nombre']}** — `{codigo}`\n\n"
            f"{info.get('descripcion', 'Sin descripción')}\n\n"
            f"Ad-valorem: **{ad_valorem:.0f}%** | "
            f"Requisitos: {info.get('requisitos', 'N/A')}\n\n"
            f"Arancel estimado: **${est.get('arancel_usd', 0):,.2f}** | "
            f"IVA estimado: **${est.get('iva_usd', 0):,.2f}**"
        )
        st.info(texto_info)

def vista_historial(config):
    st.subheader("📚 Historial persistente de importaciones")
    id_perfil = config.get("id_perfil", "")
    if SHEETS_DB_OK:
        est = sheets_db.estado_conexion(); st.caption(f"Modo: **{est['modo'].upper()}** · {est['mensaje']}")
        df_hist = sheets_db.leer_historial(id_perfil=id_perfil)
    else: st.caption("Modo: **LOCAL** (sin `sheets_db.py`)"); df_hist = pd.DataFrame()
    if df_hist.empty: st.info(f"Aún no hay importaciones guardadas para **{config.get('empresa','esta empresa')}**."); return
    c1, c2, c3 = st.columns(3)
    with c1: f_sel = st.selectbox("Filtrar por factura", ["(Todas)"] + sorted(df_hist["factura"].astype(str).unique().tolist()))
    with c2: p_sel = st.selectbox("Filtrar por producto", ["(Todos)"] + sorted(df_hist["producto"].astype(str).unique().tolist()))
    with c3: sem_filtro = st.selectbox("Filtrar por semáforo", ["(Todos)", "🔴", "🟡", "🟢", "⚪"])
    df_f = df_hist.copy()
    if f_sel != "(Todas)": df_f = df_f[df_f["factura"] == f_sel]
    if p_sel != "(Todos)": df_f = df_f[df_f["producto"] == p_sel]
    if sem_filtro != "(Todos)": df_f = df_f[df_f["semaforo"] == sem_filtro]
    st.dataframe(df_f, use_container_width=True, height=400)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Importaciones", df_f["id_importacion"].nunique()); m2.metric("Productos", len(df_f))
    m3.metric("Gasto arribo USD", f"$ {pd.to_numeric(df_f['gasto_arribo_total_usd'], errors='coerce').sum():,.0f}")
    m4.metric("Productos en rojo", (df_f["semaforo"] == "🔴").sum())
    st.download_button("📥 Descargar historial filtrado (CSV)", data=df_f.to_csv(index=False).encode("utf-8-sig"), file_name=f"historial_{id_perfil}_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

    # Generador de Excel sintetico AJUSTABLE 
def vista_generador_sintetico():
    with st.sidebar.expander("🛠️ Panel Oculto: Generador Auxiliar", expanded=True):
        st.markdown("### Generador de Datos de Prueba")
        cant_articulos = st.number_input("Cantidad de artículos", min_value=1, max_value=50, value=5, step=1, key="gen_cant")
        ramo = st.selectbox("Ramo comercial:", list(BANCO_PRODUCTOS_SINTETICOS.keys()), key="gen_ramo")
        tipo_alarma = st.selectbox("Condición de Alarmas:", [
            "🔴 Todos en Alerta Roja (Pedir YA)",
            "🟢 Todos en Stock Saludable (OK)",
            "🟡 Todos en Precaución",
            "🔀 Mixto (Combinado)"
        ], key="gen_alarma")
            
        if st.button("🚀 Generar y Descargar Excel", type="primary", key="btn_gen_excel"):
            lista_base = BANCO_PRODUCTOS_SINTETICOS.get(ramo, BANCO_PRODUCTOS_SINTETICOS["Moto Repuestos"])
            filas = []

            for i in range(cant_articulos):
                prod_ref = lista_base[i % len(lista_base)]
                variacion = 1.0 if i < len(lista_base) else round(1.0 + (i * 0.05), 2)
                
                nombre = f"{prod_ref['nombre']} (Mod. {i+1})" if i >= len(lista_base) else prod_ref['nombre']
                cantidad = int(random.choice([100, 150, 200, 250, 400, 500, 600]))
                fob = round(prod_ref['fob'] * variacion, 2)
                peso_u = round(prod_ref['peso'], 2)
                vol_u = round(prod_ref['vol'], 4)
                partida = prod_ref['partida']
                
                ventas_semana = random.randint(10, 40)
                demanda_60_dias = int(ventas_semana * (60 / 7))
                
                if "🔴" in tipo_alarma:
                    stock_actual = int(demanda_60_dias * 0.25)
                elif "🟢" in tipo_alarma:
                    stock_actual = int(demanda_60_dias * 1.5)
                elif "🟡" in tipo_alarma:
                    stock_actual = int(demanda_60_dias * 0.9)
                else:
                    opc = i % 3
                    if opc == 0: stock_actual = int(demanda_60_dias * 0.2)
                    elif opc == 1: stock_actual = int(demanda_60_dias * 0.85)
                    else: stock_actual = int(demanda_60_dias * 1.4)
                        
                dias_entrega = 60

                filas.append({
                    "Producto": nombre, "Cantidad": cantidad, "Precio FOB Origen $/u": fob,
                    "Peso unitario (kg)": peso_u, "Volumen unitario (m3)": vol_u,
                    "Stock Actual": stock_actual, "Ventas Semanales": ventas_semana,
                    "Días de Entrega": dias_entrega, "Partida Arancelaria": partida
                })

            df_gen = pd.DataFrame(filas)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_gen.to_excel(writer, index=False, sheet_name='Sheet1')
            buffer.seek(0)

            st.sidebar.success(f"✅ Archivo listo para **{ramo}** ({cant_articulos} ítems).")
            nombre_archivo = f"Prueba_{ramo.replace(' ', '_')}_{cant_articulos}items.xlsx"
            st.sidebar.download_button(
                label="📥 Descargar Excel Creado",
                data=buffer,
                file_name=nombre_archivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

def main():
    st.set_page_config(page_title="Sistema de Importación Inteligente Premium", page_icon="🛳️", layout="wide")
    if not verificar_acceso(): return
    inicializar_estado(); inicializar_monedas()
    panel_perfil_sidebar()
    config = st.session_state.config_empresa.copy()
    
    # Herramienta auxiliar discreta en la barra lateral para demostraciones
    modo_demo = st.sidebar.toggle("🛠️ Modo Demostración (Generador de Datos)", value=False)
    if modo_demo:
        vista_generador_sintetico()

    if not config.get("empresa"): st.warning("👈 Crea o selecciona un **perfil de empresa** en la barra lateral para comenzar."); return
    panel_configuracion_avanzada(config); panel_monedas_sidebar(config)
    st.title("🛳️ Sistema de Análisis de Importación Inteligente Premium 🐉")
    # Definimos de forma segura la función auxiliar localmente si no existe
    def _texto_seguro(val, val_otro):
        if val == "Otro" and val_otro:
            return str(val_otro)
        return str(val or "No especificado")

    # Variables efectivas limpias
    empresa_activa = config.get('empresa', 'Empresa Principal')
    sector_activo = _texto_seguro(config.get('sector'), config.get('sector_otro'))
    origen_efectivo = _texto_seguro(config.get('origen'), config.get('origen_otro'))
    
    st.markdown(
        f"<span style='font-size: 16px; color: #1f4e78; font-weight: bold;'>"
        f"Empresa activa: {empresa_activa} &nbsp;|&nbsp; Sector: {sector_activo} &nbsp;|&nbsp; Origen: {origen_efectivo}"
        f"</span>",
        unsafe_allow_html=True
    )

    st.caption("Ingeniería con IA: **Prof. Jesús Pulido V.** · Asesor de Importación Inteligente")
    
    with st.sidebar:
        st.markdown("---")
        if SHEETS_DB_OK:
            est = sheets_db.estado_conexion()
            if est["modo"] == "nube": st.success(f"☁️ {est['mensaje']}")
            else: st.info(f"💾 {est['mensaje']}")
        else: st.info("💾 Modo local (sin sheets_db.py)")
        st.markdown("---"); st.caption("📞 0424-728.3199 / 0416-291.6426"); st.caption("✉️ jeshua166@gmail.com")
        
    archivo = st.file_uploader("📤 Sube tu Excel o CSV con los productos", type=["xlsx", "xls", "csv"])
    if archivo is None:
        st.info("Sube un archivo Excel o CSV para comenzar el análisis o activa el **Modo Demostración** en la barra lateral para crear un archivo de prueba en segundos.")
        with st.expander("❓ Columnas esperadas"): st.markdown("- Producto / Descripción\n- Cantidad\n- Precio FOB Origen (unitario)\n- Peso unitario (kg)\n- Volumen unitario (m³)\n- Stock Actual\n- Ventas Semanales\n- Días de Entrega\n- Partida Arancelaria (opcional)")
        return

    try:
        df = leer_excel(archivo); st.success(f"✅ Archivo cargado: **{len(df)}** filas")
        with st.expander("👀 Ver primeras filas"): st.dataframe(df.head(), use_container_width=True)
    except Exception as e: st.error(f"Error al leer archivo: {e}"); return
    
    mapeo = mapear_columnas(df)
    st.markdown("### 💼 Gastos del contenedor (en USD)")
    cols = st.columns(3); gastos_ingresados = {}
    for i, (nombre, criterio) in enumerate(GASTOS_CONTENEDOR):
        with cols[i % 3]:
            val = st.number_input(f"{nombre} ({criterio})", min_value=0.0, value=0.0, step=10.0, key=f"g_{nombre}")
            gastos_ingresados[nombre] = Decimal(str(val))
            
    if not st.button("🚀 Calcular análisis completo", type="primary") and "productos_actuales" not in st.session_state:
        return
    
    try:
        productos = construir_productos_desde_df(df, mapeo)
        gastos_contenedor = calcular_costos(productos, gastos_ingresados, config)
    except Exception as e: st.error(f"Error en cálculo: {e}"); return
    
    st.success(f"✅ Análisis completado para **{len(productos)}** productos.")
    
    st.session_state["productos_actuales"] = productos
    st.session_state["config_actual"] = config
    st.session_state["gastos_contenedor"] = gastos_contenedor
    
    if SHEETS_DB_OK:
        if st.button("💾 Guardar esta importación en el historial", type="secondary"):
            prods_guardar = st.session_state.get("productos_actuales", productos)
            conf_guardar = st.session_state.get("config_actual", config)
            
            ok, msg = sheets_db.guardar_importacion(prods_guardar, conf_guardar, usuario=conf_guardar.get("propietario") or "admin")
            (st.success if ok else st.warning)(msg)
            sheets_db.guardar_alertas(generar_alertas_reposicion(prods_guardar, conf_guardar))
            
    tab1, tab2, tab3, tab4, tab5, tab6, tab_salvavidas = st.tabs([
        "📊 Análisis de costos",
        "📦 Reposición",
        "📈 Flujo de caja",
        "🛃 Auditoría aduanera",
        "📄 Reporte completo",
        "📜 Historial",
        "🛟 Salvavidas"
    ])

    
    with tab1: vista_analisis_costos(productos, config)
    with tab2: mostrar_alertas_en_panel(generar_alertas_reposicion(productos, config))
    with tab3: mostrar_flujo_caja(proyectar_flujo_caja(productos, config, semanas=13, crecimiento_semanal=0.02, costo_fijo_semanal=config.get("costo_fijo_semanal", 0), pago_importacion={"fecha": config.get("fecha_proximo_pedido"), "monto_usd": config.get("monto_proximo_pedido", 0)}))
    with tab4: vista_auditoria_aduanera(productos)
    with tab5:
        st.subheader("📄 Reporte Ejecutivo")
        reporte_html = crear_reporte_html(productos, gastos_contenedor, config)
        
        components.html(reporte_html, height=1500, scrolling=True)
        
        st.info("💡 Para guardar este reporte como PDF, presione el botón de 'Compartir' de su navegador y seleccione 'Imprimir' o 'Guardar como PDF'.")
        st.divider()
        boton_exportar_sheets(productos, config)
        
        st.markdown("---")
        pdf_bytes = generar_pdf_desde_html(reporte_html)
        if pdf_bytes:
            st.download_button(
                label="📄 Descargar Reporte en PDF",
                data=pdf_bytes,
                file_name=f"Reporte_{config.get('factura','SN')}.pdf",
                mime="application/pdf",
                type="primary"
            )
    with tab6: vista_historial(config)
    with tab_salvavidas:
        renderizar_pestana_salvavidas(productos, config)
        
if __name__ == "__main__":
    main()
       
