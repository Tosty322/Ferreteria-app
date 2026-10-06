from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# --- CONEXIÓN A SUPABASE ---
def conectar_db():
    return st.connection("postgresql", type="sql")

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Ferretería Sincronizada", layout="wide")
st.title("🛠️ Sistema de Control y Ventas - Ferretería")

# Listas globales de categorías
CATEGORIAS_DISPONIBLES = [
    "Gasfitería", "Electricidad", "Construcción", "Herramientas",
    "Pinturas", "Plásticos", "Limpieza", "Iluminación", "Otros",
]

CATEGORIAS_GASTOS = [
    "Comida y bebida",
    "Compras para el local",
    "Luis",
    "Percy",
]

# --- MENÚ LATERAL DIVIDIDO EN DOS BLOQUES VERTICALES ---
st.sidebar.title("Menú de Navegación")

st.sidebar.markdown("### 📋 Operaciones Diarias")
menu_diarias = st.sidebar.radio(
    "Seleccione operación diaria:",
    [
        "Ninguna",
        "Registrar Venta (POS)",
        "Control de Gastos",
        "Corte de Caja y Balance",
        "Productos Faltantes",
        "Historial de Ventas",
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")

st.sidebar.markdown("### 📦 Gestión de Inventario y Proveedores")
menu_gestion = st.sidebar.radio(
    "Seleccione gestión:",
    [
        "Ninguna",
        "Inventario Actual",
        "Gestión de Proveedores",
        "Registrar Producto",
        "Modificar Datos del Producto",
        "Registrar Compra / Reposición",
        "Historial de Compras",
        "Actualizar Precios",
        "Historial de Precios",
        "Eliminar Producto",
    ],
    label_visibility="collapsed"
)

# Definir qué menú tiene prioridad activa
if menu_diarias != "Ninguna":
    menu = menu_diarias
elif menu_gestion != "Ninguna":
    menu = menu_gestion
else:
    menu = "Inventario Actual"

# -------------------------------------------------------------
# 1. INVENTARIO ACTUAL
# -------------------------------------------------------------
if menu == "Inventario Actual":
    conn = conectar_db()
    st.header("📦 Inventario Actual y Stock Total")
    
    # Obtener lista de proveedores para el filtro
    df_prov_inv = conn.query("SELECT id, nombre FROM proveedores", ttl=0)
    proveedores_filtro_dict = dict(zip(df_prov_inv["nombre"], df_prov_inv["id"])) if not df_prov_inv.empty else {}
    
    query_inv_total = "SELECT p.stock, p.precio_compra, p.precio_venta FROM productos p"
    df_todos = conn.query(query_inv_total, ttl=0)
    
    if not df_todos.empty:
        total_items = len(df_todos)
        stock_total_unidades = df_todos["stock"].sum()
        valor_inventario_compra = (df_todos["stock"] * df_todos["precio_compra"]).sum()
        valor_inventario_venta = (df_todos["stock"] * df_todos["precio_venta"]).sum()
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Variedad de Productos", f"{total_items} ítems")
        col_m2.metric("Stock Total de Unidades", f"{stock_total_unidades:,.5f}")
        col_m3.metric("Valor Inventario (Costo)", f"S/ {valor_inventario_compra:,.5f}")
    
    st.divider()
    
    # Filtros avanzados de categoría y proveedor
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_filtro_inv = st.selectbox("📂 Filtrar por categoría:", ["Todas las Categorías"] + CATEGORIAS_DISPONIBLES, key="filtro_inv")
    with col_f2:
        lista_prov_nombres = ["Todos los Proveedores"] + list(proveedores_filtro_dict.keys())
        prov_filtro_inv = st.selectbox("🤝 Filtrar por proveedor:", lista_prov_nombres, key="filtro_prov_inv")
        
    busqueda_inv = st.text_input("🔍 Buscar producto por nombre o código en el inventario:")
    
    query = """
        SELECT p.id, p.codigo_interno, p.nombre, p.categoria, p.unidad_medida, 
               p.stock, p.precio_venta, p.precio_compra, pr.nombre AS proveedor
        FROM productos p
        LEFT JOIN proveedores pr ON p.proveedor_id = pr.id
        WHERE 1=1
    """
    if cat_filtro_inv != "Todas las Categorías":
        query += f" AND p.categoria = '{cat_filtro_inv}'"
    if prov_filtro_inv != "Todos los Proveedores":
        prov_id_sel = proveedores_filtro_dict.get(prov_filtro_inv)
        if prov_id_sel:
            query += f" AND p.proveedor_id = {prov_id_sel}"
    if busqueda_inv:
        query += f" AND (p.nombre ILIKE '%{busqueda_inv}%' OR p.codigo_interno ILIKE '%{busqueda_inv}%')"
        
    df_productos = conn.query(query, ttl=0)
    if df_productos.empty:
        st.info("No se encontraron productos con ese criterio.")
    else:
        st.dataframe(df_productos, use_container_width=True)

# -------------------------------------------------------------
# 2. GESTIÓN DE PROVEEDORES
# -------------------------------------------------------------
elif menu == "Gestión de Proveedores":
    st.header("🤝 Gestión y Registro de Proveedores")
    conn = conectar_db()
    
    with st.form("form_proveedor"):
        st.subheader("➕ Registrar Nuevo Proveedor")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            nombre_prov = st.text_input("Nombre / Empresa del Proveedor")
            contacto_prov = st.text_input("Persona de Contacto (Opcional)")
        with col_p2:
            telefono_prov = st.text_input("Teléfono / Celular")
            direccion_prov = st.text_input("Dirección (Opcional)")
            
        submit_prov = st.form_submit_button("Guardar Proveedor")
        if submit_prov:
            if nombre_prov:
                try:
                    with conn.session as s:
                        s.execute(
                            text("""
                                INSERT INTO proveedores (nombre, contacto, telefono, direccion)
                                VALUES (:nombre, :contacto, :telefono, :direccion)
                            """),
                            dict(nombre=nombre_prov, contacto=contacto_prov, telefono=telefono_prov, direccion=direccion_prov),
                        )
                        s.commit()
                    st.success(f"¡Proveedor '{nombre_prov}' registrado con éxito!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar el proveedor: {e}")
            else:
                st.warning("El nombre del proveedor es obligatorio.")
                
    st.divider()
    st.subheader("📋 Lista de Proveedores Registrados")
    df_proveedores = conn.query("SELECT * FROM proveedores", ttl=0)
    if df_proveedores.empty:
        st.info("No hay proveedores registrados todavía.")
    else:
        st.dataframe(df_proveedores, use_container_width=True)

# -------------------------------------------------------------
# 3. REGISTRAR PRODUCTO
# -------------------------------------------------------------
elif menu == "Registrar Producto":
    st.header("➕ Registrar Nuevo Producto")
    conn = conectar_db()
    
    df_prov = conn.query("SELECT id, nombre FROM proveedores", ttl=0)
    proveedores_dict = {}
    if not df_prov.empty:
        proveedores_dict = dict(zip(df_prov["nombre"], df_prov["id"]))
    
    with st.form("form_producto"):
        col1, col2 = st.columns(2)
        with col1:
            codigo = st.text_input("Código Interno (Ej: TUB-001)")
            nombre = st.text_input('Nombre del Producto (Ej: Tubo PVC Desagüe 4")')
            categoria = st.selectbox("Categoría", CATEGORIAS_DISPONIBLES)
            if proveedores_dict:
                lista_nombres_prov = list(proveedores_dict.keys())
                prov_seleccionado = st.selectbox("Proveedor", lista_nombres_prov)
            else:
                st.warning("⚠️ No hay proveedores registrados.")
                prov_seleccionado = None

        with col2:
            unidad = st.selectbox("Unidad de Medida", ["Unidad", "Docena", "Metro", "Kilo", "Litro", "Caja"])
            stock = st.number_input("Stock Inicial", min_value=0.0, value=0.00001, step=0.00001, format="%.5f")
            precio_venta = st.number_input("Precio de Venta (S/)", min_value=0.0, value=0.00001, step=0.00001, format="%.5f")
            precio_compra = st.number_input("Precio de Compra / Costo (S/)", min_value=0.0, value=0.00001, step=0.00001, format="%.5f")
            
        submit = st.form_submit_button("Guardar Producto")
        if submit:
            if codigo and nombre:
                try:
                    prov_id = proveedores_dict.get(prov_seleccionado) if prov_seleccionado else None
                    with conn.session as s:
                        s.execute(
                            text("""
                                INSERT INTO productos (codigo_interno, nombre, categoria, unidad_medida, stock, precio_venta, precio_compra, proveedor_id)
                                VALUES (:codigo, :nombre, :categoria, :unidad, :stock, :precio_venta, :precio_compra, :prov_id)
                            """),
                            dict(codigo=codigo, nombre=nombre, categoria=categoria, unidad=unidad, stock=stock, precio_venta=precio_venta, precio_compra=precio_compra, prov_id=prov_id),
                        )
                        s.commit()
                    st.success(f"¡Producto '{nombre}' registrado con éxito!")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
            else:
                st.warning("Completa al menos el código y el nombre.")

# -------------------------------------------------------------
# 4. MODIFICAR DATOS DEL PRODUCTO
# -------------------------------------------------------------
elif menu == "Modificar Datos del Producto":
    st.header("✏️ Modificar Datos, Categoría o Proveedor de Producto")
    conn = conectar_db()
    
    df_prov = conn.query("SELECT id, nombre FROM proveedores", ttl=0)
    proveedores_dict = dict(zip(df_prov["nombre"], df_prov["id"])) if not df_prov.empty else {}
    
    cat_filtro_mod = st.selectbox("📂 Filtrar productos por categoría:", ["Todas las Categorías"] + CATEGORIAS_DISPONIBLES)
    busqueda_edit = st.text_input("🔍 Escribe para buscar el producto (por nombre o código):")
    
    query_edit = "SELECT id, codigo_interno, nombre, categoria, unidad_medida, proveedor_id FROM productos WHERE 1=1"
    if cat_filtro_mod != "Todas las Categorías":
        query_edit += f" AND categoria = '{cat_filtro_mod}'"
    if busqueda_edit:
        query_edit += f" AND (nombre ILIKE '%{busqueda_edit}%' OR codigo_interno ILIKE '%{busqueda_edit}%')"
        
    df_prod_edit = conn.query(query_edit, ttl=0)
    if df_prod_edit.empty:
        st.info("No se encontró ningún producto con los filtros seleccionados.")
    else:
        df_prod_edit["opcion_modificar"] = (
            df_prod_edit["nombre"] + " [" + df_prod_edit["categoria"] + "] (Código: " + df_prod_edit["codigo_interno"] + ")"
        )
        prod_seleccionado_edit = st.selectbox("Selecciona el producto a editar:", df_prod_edit["opcion_modificar"])
        if prod_seleccionado_edit:
            idx_e = df_prod_edit[df_prod_edit["opcion_modificar"] == prod_seleccionado_edit].index[0]
            id_prod = df_prod_edit.loc[idx_e, "id"]
            cod_actual = df_prod_edit.loc[idx_e, "codigo_interno"]
            nom_actual = df_prod_edit.loc[idx_e, "nombre"]
            cat_actual = df_prod_edit.loc[idx_e, "categoria"]
            uni_actual = df_prod_edit.loc[idx_e, "unidad_medida"]
            prov_actual_id = df_prod_edit.loc[idx_e, "proveedor_id"]
            
            try:
                cat_index = CATEGORIAS_DISPONIBLES.index(cat_actual)
            except ValueError:
                cat_index = 0
                
            unidades_disponibles = ["Unidad", "Docena", "Metro", "Kilo", "Litro", "Caja"]
            try:
                uni_index = unidades_disponibles.index(uni_actual)
            except ValueError:
                uni_index = 0
                
            prov_names = list(proveedores_dict.keys())
            prov_current_name = None
            for p_name, p_id in proveedores_dict.items():
                if p_id == prov_actual_id:
                    prov_current_name = p_name
                    break
            prov_index = prov_names.index(prov_current_name) if prov_current_name in prov_names else 0

            with st.form("form_editar_datos"):
                st.write("📝 **Modifica los campos necesarios y guarda los cambios:**")
                nuevo_codigo = st.text_input("Código Interno", value=cod_actual)
                nuevo_nombre = st.text_input("Nombre del Producto", value=nom_actual)
                nueva_categoria = st.selectbox("Categoría", CATEGORIAS_DISPONIBLES, index=cat_index)
                nueva_unidad = st.selectbox("Unidad de Medida", unidades_disponibles, index=uni_index)
                nuevo_proveedor = st.selectbox("Proveedor", prov_names, index=prov_index if prov_names else 0)
                
                btn_actualizar_datos = st.form_submit_button("💾 Guardar Cambios")
                if btn_actualizar_datos:
                    if nuevo_codigo and nuevo_nombre:
                        try:
                            nuevo_prov_id = proveedores_dict.get(nuevo_proveedor) if nuevo_proveedor else None
                            with conn.session as s:
                                s.execute(
                                    text("""
                                        UPDATE productos 
                                        SET codigo_interno = :nc, nombre = :nn, categoria = :ncat, unidad_medida = :nu, proveedor_id = :nprov
                                        WHERE id = :p_id
                                    """),
                                    dict(nc=nuevo_codigo, nn=nuevo_nombre, ncat=nueva_categoria, nu=nueva_unidad, nprov=nuevo_prov_id, p_id=int(id_prod)),
                                )
                                s.commit()
                            st.success("✅ ¡Los datos del producto se actualizaron correctamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error al actualizar: {e}")
                    else:
                        st.warning("El código y el nombre no pueden estar vacíos.")

# -------------------------------------------------------------
# 5. PRODUCTOS FALTANTES
# -------------------------------------------------------------
elif menu == "Productos Faltantes":
    st.header("📝 Apuntar y Gestionar Productos Faltantes")
    conn = conectar_db()
    
    with st.form("form_faltante"):
        st.subheader("➕ Anotar nuevo producto que falta")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            nombre_faltante = st.text_input("Nombre del producto o material que falta")
            cantidad_sug = st.text_input("Cantidad aproximada / Observación (Ej: 5.5 unidades)")
            cat_faltante = st.selectbox("Categoría del Faltante", CATEGORIAS_DISPONIBLES)
        with col_f2:
            persona_apunto = st.text_input("Tu nombre (¿Quién anota este faltante?)")
            motivo_falta = st.text_input("Motivo (Ej: Se agotó, cliente pidió más)")
            
        btn_guardar_faltante = st.form_submit_button("📌 Guardar en la Lista de Faltantes")
        if btn_guardar_faltante:
            if nombre_faltante and persona_apunto:
                try:
                    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with conn.session as s:
                        s.execute(
                            text("""
                                INSERT INTO productos_faltantes
