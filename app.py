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

# Lista global de categorías disponibles
CATEGORIAS_DISPONIBLES = [
    "Gasfitería", "Electricidad", "Construcción", "Herramientas",
    "Pinturas", "Plásticos", "Limpieza", "Iluminación", "Otros",
]

st.sidebar.title("Menú de Navegación")
menu = st.sidebar.selectbox(
    "Seleccione una opción",
    [
        "Inventario Actual",
        "Gestión de Proveedores",
        "Registrar Producto",
        "Modificar Datos del Producto",
        "Productos Faltantes",
        "Registrar Compra / Reposición",
        "Historial de Compras",
        "Actualizar Precios",
        "Historial de Precios",
        "Registrar Venta (POS)",
        "Historial de Ventas",
        "Eliminar Producto",
    ],
)

# -------------------------------------------------------------
# 1. INVENTARIO ACTUAL (CON FILTRO DE CATEGORÍA)
# -------------------------------------------------------------
if menu == "Inventario Actual":
    conn = conectar_db()
    st.header("📦 Inventario Actual y Stock Total")
    
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
    
    # 📂 Filtro de categoría en el inventario actual
    cat_filtro_inv = st.selectbox("📂 Filtrar inventario por categoría:", ["Todas las Categorías"] + CATEGORIAS_DISPONIBLES, key="filtro_inv")
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
            stock = st.number_input("Stock Inicial", min_value=0.0, value=0.00000, step=0.00001, format="%.5f")
            precio_venta = st.number_input("Precio de Venta (S/)", min_value=0.0, value=0.00000, step=0.00001, format="%.5f")
            precio_compra = st.number_input("Precio de Compra / Costo (S/)", min_value=0.0, value=0.00000, step=0.00001, format="%.5f")
            
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
                    st.error(f"Error al registrar (es probable que el código '{codigo}' ya exista): {e}")
            else:
                st.warning("Completa al menos el código y el nombre.")

# -------------------------------------------------------------
# 4. MODIFICAR DATOS DEL PRODUCTO (CON FILTRO DE CATEGORÍA)
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
# 5. PRODUCTOS FALTANTES (CON FILTRO DE CATEGORÍA)
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
                                INSERT INTO productos_faltantes (nombre_producto, cantidad_sugerida, motivo, apuntado_por, fecha_hora, categoria)
                                VALUES (:nom, :cant, :mot, :per, :f_h, :cat)
                            """),
                            dict(nom=nombre_faltante, cant=cantidad_sug, mot=motivo_falta, per=persona_apunto, f_h=fecha_ahora, cat=cat_faltante),
                        )
                        s.commit()
                    st.success(f"✅ '{nombre_faltante}' fue agregado a la lista de faltantes correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar el producto faltante: {e}")
            else:
                st.warning("⚠️ Por favor, completa al menos el 'Nombre del producto' y 'Tu nombre'.")
                
    st.divider()
    st.subheader("📋 Lista Actual de Productos Faltantes")
    
    cat_filtro_faltantes = st.selectbox("📂 Filtrar lista por categoría:", ["Todas las Categorías"] + CATEGORIAS_DISPONIBLES, key="filtro_f")
    query_faltantes = "SELECT * FROM productos_faltantes"
    if cat_filtro_faltantes != "Todas las Categorías":
        query_faltantes += f" WHERE categoria = '{cat_filtro_faltantes}'"
    query_faltantes += " ORDER BY fecha_hora DESC"
    
    df_faltantes = conn.query(query_faltantes, ttl=0)
    
    if df_faltantes.empty:
        st.info("🎉 ¡Excelente noticia! No hay ningún producto faltante anotado con este filtro.")
    else:
        st.dataframe(df_faltantes, use_container_width=True)
        st.markdown("---")
        st.subheader("🗑️ Marcar como Solucionado / Eliminar Faltante")
        df_faltantes["opcion_eliminar_faltante"] = (
            "[" + df_faltantes["fecha_hora"].astype(str) + "] " + df_faltantes["nombre_producto"] + " (" + df_faltantes["categoria"].fillna("Sin categoría") + ") - Apuntado por: " + df_faltantes["apuntado_por"]
        )
        faltante_a_borrar = st.selectbox(
            "Selecciona el faltante que ya compraste o deseas quitar de la lista:",
            df_faltantes["opcion_eliminar_faltante"],
        )
        if st.button("❌ Eliminar de la lista de faltantes"):
            idx_f = df_faltantes[df_faltantes["opcion_eliminar_faltante"] == faltante_a_borrar].index[0]
            id_f_borrar = df_faltantes.loc[idx_f, "id"]
            try:
                with conn.session as s:
                    s.execute(text("DELETE FROM productos_faltantes WHERE id = :f_id"), dict(f_id=int(id_f_borrar)))
                    s.commit()
                st.success("✅ El producto fue eliminado de la lista de faltantes con éxito.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al eliminar el registro: {e}")

# -------------------------------------------------------------
# 6. REGISTRAR COMPRA / REPOSICIÓN
# -------------------------------------------------------------
elif menu == "Registrar Compra / Reposición":
    st.header("📥 Registrar Compra (Aumentar Stock y Actualizar Costos)")
    conn = conectar_db()
    busqueda_compra = st.text_input("🔍 Escribe para filtrar producto (ej: 'tubo', 'cemento'):")
    query_compra = "SELECT id, codigo_interno, nombre, stock, precio_compra, precio_venta, unidad_medida FROM productos"
    if busqueda_compra:
        query_compra += f" WHERE nombre ILIKE '%{busqueda_compra}%' OR codigo_interno ILIKE '%{busqueda_compra}%'"
    df_prod_compra = conn.query(query_compra, ttl=0)
    if df_prod_compra.empty:
        st.warning("No se encontró ningún producto con ese criterio.")
    else:
        df_prod_compra["opcion_compra"] = (
            df_prod_compra["nombre"] + " [Unidad: " + df_prod_compra["unidad_medida"] + "] (Stock: " + df_prod_compra["stock"].astype(str) + " - Cod: " + df_prod_compra["codigo_interno"] + ")"
        )
        prod_seleccionado = st.selectbox("Selecciona el producto filtrado:", df_prod_compra["opcion_compra"])
        if prod_seleccionado:
            idx = df_prod_compra[df_prod_compra["opcion_compra"] == prod_seleccionado].index[0]
            p_id = df_prod_compra.loc[idx, "id"]
            stock_actual = df_prod_compra.loc[idx, "stock"]
            c_actual = df_prod_compra.loc[idx, "precio_compra"]
            v_actual = df_prod_compra.loc[idx, "precio_venta"]
            u_medida = df_prod_compra.loc[idx, "unidad_medida"]
            st.info(f"📏 **Unidad de Medida:** {u_medida}  |  📦 **Stock actual:** {stock_actual:,.5f} {u_medida}  |  🏷️ **Precio Compra:** S/ {c_actual:,.5f}  |  💰 **Precio Venta:** S/ {v_actual:,.5f}")
            with st.form("form_compra_stock"):
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    cantidad_a_comprar = st.number_input(f"Cantidad a sumar al stock ({u_medida})", min_value=0.00001, value=1.00000, step=0.00001, format="%.5f")
                    nuevo_precio_compra = st.number_input("Nuevo Precio de Compra / Costo unitario (S/)", min_value=0.0, value=float(c_actual), step=0.00001, format="%.5f")
                with col_c2:
                    nuevo_precio_venta = st.number_input("Nuevo Precio de Venta (S/)", min_value=0.0, value=float(v_actual), step=0.00001, format="%.5f")
                    st.write("")
                    st.write(f"**Costo Total de la Compra:** S/ {(cantidad_a_comprar * nuevo_precio_compra):,.5f}")
                btn_guardar_compra = st.form_submit_button("➕ Registrar Compra y Actualizar Inventario")
                if btn_guardar_compra:
                    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    nuevo_stock_total = stock_actual + cantidad_a_comprar
                    costo_total_compra = cantidad_a_comprar * nuevo_precio_compra
                    with conn.session as s:
                        s.execute(
                            text("""
                                INSERT INTO compras (producto_id, cantidad, precio_compra_anterior, precio_compra_nuevo, precio_venta_anterior, precio_venta_nuevo, costo_total, fecha_hora)
                                VALUES (:p_id, :cant, :p_c_ant, :p_c_nue, :p_v_ant, :p_v_nue, :c_tot, :f_h)
                            """),
                            dict(p_id=int(p_id), cant=float(cantidad_a_comprar), p_c_ant=float(c_actual), p_c_nue=float(nuevo_precio_compra), p_v_ant=float(v_actual), p_v_nue=float(nuevo_precio_venta), c_tot=float(costo_total_compra), f_h=fecha_ahora),
                        )
                        s.execute(
                            text("""
                                UPDATE productos 
                                SET stock = :n_stock, precio_compra = :n_p_compra, precio_venta = :n_p_venta
                                WHERE id = :p_id
                            """),
                            dict(n_stock=float(nuevo_stock_total), n_p_compra=float(nuevo_precio_compra), n_p_venta=float(nuevo_precio_venta), p_id=int(p_id)),
                        )
                        if nuevo_precio_venta != v_actual:
                            s.execute(
                                text("""
                                    INSERT INTO historial_precios (producto_id, precio_anterior, precio_nuevo, fecha_cambio)
                                    VALUES (:p_id, :v_ant, :v_nue, :f_h)
                                """),
                                dict(p_id=int(p_id), v_ant=float(v_actual), v_nue=float(nuevo_precio_venta), f_h=fecha_ahora),
                            )
                        s.commit()
                    st.success(f"🎉 ¡Compra registrada con éxito! Stock actualizado a {nuevo_stock_total:,.5f} {u_medida}.")
                    st.rerun()

# -------------------------------------------------------------
# 7. HISTORIAL DE COMPRAS
# -------------------------------------------------------------
elif menu == "Historial de Compras":
    st.header("📋 Historial de Compras y Reposiciones")
    conn = conectar_db()
    query_compras = """
        SELECT c.id AS id_compra, c.fecha_hora, p.codigo_interno, p.nombre AS producto, 
               c.cantidad, p.unidad_medida, c.precio_compra_anterior, c.precio_compra_nuevo, 
               c.precio_venta_anterior, c.precio_venta_nuevo, c.costo_total
        FROM compras c
        JOIN productos p ON c.producto_id = p.id
        ORDER BY c.fecha_hora DESC
    """
    df_compras = conn.query(query_compras, ttl=0)
    if df_compras.empty:
        st.info("Aún no se han registrado compras de mercadería.")
    else:
        st.dataframe(df_compras, use_container_width=True)
        csv_compras = df_compras.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar Historial de Compras en CSV",
            data=csv_compras,
            file_name=f"historial_compras_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv",
            mime="text/csv",
        )

# -------------------------------------------------------------
# 8. ACTUALIZAR PRECIOS
# -------------------------------------------------------------
elif menu == "Actualizar Precios":
    st.header("🔄 Actualizar Precios Independiente")
    conn = conectar_db()
    df_productos = conn.query("SELECT id, codigo_interno, nombre, precio_venta FROM productos", ttl=0)
    if df_productos.empty:
        st.info("No hay productos para actualizar.")
    else:
        df_productos["opcion_combo"] = df_productos["nombre"] + " (Cod: " + df_productos["codigo_interno"] + ")"
        producto_seleccionado = st.selectbox("Selecciona el producto a modificar:", df_productos["opcion_combo"])
        if producto_seleccionado:
            idx = df_productos[df_productos["opcion_combo"] == producto_seleccionado].index[0]
            prod_id = df_productos.loc[idx, "id"]
            precio_actual = df_productos.loc[idx, "precio_venta"]
            st.write(f"**Precio de venta actual:** S/ {precio_actual:,.5f}")
            nuevo_precio = st.number_input("Nuevo Precio de Venta (S/)", min_value=0.0, value=float(precio_actual), step=0.00001, format="%.5f")
            if st.button("Guardar Nuevo Precio"):
                if nuevo_precio != precio_actual:
                    fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with conn.session as s:
                        s.execute(
                            text("""
                                INSERT INTO historial_precios (producto_id, precio_anterior, precio_nuevo, fecha_cambio)
                                VALUES (:p_id, :p_ant, :p_nue, :f_h)
                            """),
                            dict(p_id=int(prod_id), p_ant=float(precio_actual), p_nue=float(nuevo_precio), f_h=fecha_ahora),
                        )
                        s.execute(text("UPDATE productos SET precio_venta = :n_p WHERE id = :p_id"), dict(n_p=float(nuevo_precio), p_id=int(prod_id)))
                        s.commit()
                    st.success("¡Precio actualizado y registrado en el historial!")
                    st.rerun()
                else:
                    st.info("El nuevo precio es idéntico al actual.")

# -------------------------------------------------------------
# 9. HISTORIAL DE PRECIOS
# -------------------------------------------------------------
elif menu == "Historial de Precios":
    st.header("📈 Historial de Cambios de Precios")
    conn = conectar_db()
    query = """
        SELECT hp.id, p.codigo_interno, p.nombre, hp.precio_anterior, hp.precio_nuevo, hp.fecha_cambio
        FROM historial_precios hp
        JOIN productos p ON hp.producto_id = p.id
        ORDER BY hp.fecha_cambio DESC
    """
    df_historial = conn.query(query, ttl=0)
    if df_historial.empty:
        st.info("Aún no se han registrado cambios de precios.")
    else:
        st.dataframe(df_historial, use_container_width=True)

# -------------------------------------------------------------
# 10. REGISTRAR VENTA (POS)
# -------------------------------------------------------------
elif menu == "Registrar Venta (POS)":
    st.header("🛒 Caja / Punto de Venta")
    conn = conectar_db()
    filtro_pos = st.text_input("🔍 Escribe para filtrar producto (ej: 'cemento', 'clavo'):")
    query_pos = "SELECT id, codigo_interno, nombre, stock, precio_venta, unidad_medida FROM productos"
    if filtro_pos:
        query_pos += f" WHERE nombre ILIKE '%{filtro_pos}%' OR codigo_interno ILIKE '%{filtro_pos}%'"
    df_productos = conn.query(query_pos, ttl=0)
    if df_productos.empty:
        st.warning("No se encontró ningún producto registrado.")
    else:
        if "carrito" not in st.session_state:
            st.session_state.carrito = []
        df_productos["opcion_pos"] = (
            df_productos["nombre"] + " ➡️ [Unidad: " + df_productos["unidad_medida"] + "] | Stock: " + df_productos["stock"].map('{:,.5f}'.format) + " | S/ " + df_productos["precio_venta"].map('{:,.5f}'.format)
        )
        col_select, col_cant = st.columns([3, 1])
        with col_select:
            prod_elegido = st.selectbox("Selecciona el producto filtrado:", df_productos["opcion_pos"])
        with col_cant:
            idx_sel = df_productos[df_productos["opcion_pos"] == prod_elegido].index[0]
            unidad_sel = df_productos.loc[idx_sel, "unidad_medida"]
            cantidad_vender = st.number_input(f"Cantidad ({unidad_sel})", min_value=0.00001, value=1.00000, step=0.00001, format="%.5f")
        if st.button("➕ Agregar al Carrito"):
            p_id = df_productos.loc[idx_sel, "id"]
            p_nombre = df_productos.loc[idx_sel, "nombre"]
            p_stock = df_productos.loc[idx_sel, "stock"]
            p_precio = df_productos.loc[idx_sel, "precio_venta"]
            if cantidad_vender > p_stock:
                st.error(f"¡Stock insuficiente! Stock disponible: {p_stock:,.5f} {unidad_sel}")
            else:
                st.session_state.carrito.append({
                    "id": int(p_id), "nombre": p_nombre, "cantidad": float(cantidad_vender),
                    "precio": float(p_precio), "subtotal": float(cantidad_vender * p_precio),
                })
                st.success(f"Agregado: {p_nombre} ({cantidad_vender:,.5f} {unidad_sel})")
        if st.session_state.carrito:
            st.subheader("🛍️️ Productos en el Ticket Actual")
            df_carrito = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_carrito[["nombre", "cantidad", "precio", "subtotal"]], use_container_width=True)
            total_original = df_carrito["subtotal"].sum()
            st.write(f"Subtotal de productos sin descuento: **S/ {total_original:,.5f}**")
            st.subheader("🏷️ Ajuste de Precio / Descuento")
            total_venta = st.number_input("Total Final a Cobrar al Cliente (S/):", min_value=0.01, value=float(total_original), step=0.00001, format="%.5f")
            st.subheader("💳 Modalidad de Pago")
            metodo_pago = st.selectbox("Forma principal / Tipo", ["Efectivo", "Yape / Plin", "Mixto (Yape/Plin + Efectivo)", "Tarjeta"])
            monto_yape = 0.0
            monto_efectivo = 0.0
            if metodo_pago == "Mixto (Yape/Plin + Efectivo)":
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    monto_yape = st.number_input("Monto pagado con Yape/Plin (S/)", min_value=0.0, max_value=float(total_venta), value=float(total_venta) / 2, step=0.00001, format="%.5f")
                with col_p2:
                    monto_efectivo = total_venta - monto_yape
                    st.write(f"Monto automático en Efectivo: **S/ {monto_efectivo:,.5f}**")
            elif metodo_pago == "Yape / Plin":
                monto_yape = total_venta
            elif metodo_pago == "Efectivo":
                monto_efectivo = total_venta
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✅ Confirmar y Registrar Venta (Generar Boleta)"):
                    try:
                        fecha_venta = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        with conn.session as s:
                            res = s.execute(
                                text("""
                                    INSERT INTO ventas (fecha_hora, total, metodo_pago, monto_yape, monto_efectivo)
                                    VALUES (:f_h, :tot, :m_p, :m_y, :m_e)
                                    RETURNING id
                                """),
                                dict(f_h=fecha_venta, tot=float(total_venta), m_p=metodo_pago, m_y=float(monto_yape), m_e=float(monto_efectivo)),
                            )
                            venta_id = res.fetchone()[0]
                            factor = total_venta / total_original if total_original > 0 else 1.0
                            for item in st.session_state.carrito:
                                subtotal_proporcional = item["subtotal"] * factor
                                precio_unitario_proporcional = subtotal_proporcional / item["cantidad"]
                                s.execute(
                                    text("""
                                        INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                                        VALUES (:v_id, :p_id, :cant, :p_u, :sub)
                                    """),
                                    dict(v_id=int(venta_id), p_id=int(item["id"]), cant=float(item["cantidad"]), p_u=float(precio_unitario_proporcional), sub=float(subtotal_proporcional)),
                                )
                                s.execute(text("UPDATE productos SET stock = stock - :cant WHERE id = :p_id"), dict(cant=float(item["cantidad"]), p_id=int(item["id"])))
                            s.commit()
                        st.success(f"🎉 ¡Venta registrada con éxito! **N° de Boleta: #{venta_id:04d}**")
                        st.session_state.carrito = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al guardar la venta: {e}")
            with col_btn2:
                if st.button("🗑️ Vaciar Carrito"):
                    st.session_state.carrito = []
                    st.rerun()

# -------------------------------------------------------------
# 11. HISTORIAL DE VENTAS
# -------------------------------------------------------------
elif menu == "Historial de Ventas":
    st.header("📊 Historial de Ventas y Boletas Detallado")
    conn = conectar_db()
    query_historial_completo = """
        SELECT v.id AS n_boleta, v.fecha_hora, p.nombre AS producto, dv.cantidad, 
               p.unidad_medida, dv.precio_unitario, dv.subtotal, v.metodo_pago, 
               v.monto_yape, v.monto_efectivo, v.total AS total_boleta
        FROM detalle_ventas dv
        JOIN ventas v ON dv.venta_id = v.id
        JOIN productos p ON dv.producto_id = p.id
        ORDER BY v.id DESC, v.fecha_hora DESC
    """
    df_historial = conn.query(query_historial_completo, ttl=0)
    if df_historial.empty:
        st.info("No hay ventas registradas todavía.")
    else:
        df_historial["n_boleta"] = df_historial["n_boleta"].apply(lambda x: f"#{int(x):04d}")
        st.dataframe(df_historial, use_container_width=True)
        csv_data = df_historial.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar Historial Detallado en Excel (CSV)",
            data=csv_data,
            file_name=f"historial_ventas_boletas_{datetime.now().strftime('%Y-%m-%d')}.csv",
            mime="text/csv",
        )

# -------------------------------------------------------------
# 12. ELIMINAR PRODUCTO
# -------------------------------------------------------------
elif menu == "Eliminar Producto":
    st.header("🗑️ Eliminar Producto del Inventario")
    st.warning("⚠️ **Precaución:** Se recomienda pasar a stock 0 en lugar de eliminar si tiene historial.")
    conn = conectar_db()
    busqueda_del = st.text_input("🔍 Escribe para buscar el producto que deseas eliminar (por nombre o código):")
    query_del = "SELECT id, codigo_interno, nombre, stock, precio_venta, unidad_medida FROM productos"
    if busqueda_del:
        query_del += f" WHERE nombre ILIKE '%{busqueda_del}%' OR codigo_interno ILIKE '%{busqueda_del}%'"
    df_prod_del = conn.query(query_del, ttl=0)
    if df_prod_del.empty:
        st.info("No se encontró ningún producto.")
    else:
        df_prod_del["opcion_eliminar"] = df_prod_del["nombre"] + " [Código: " + df_prod_del["codigo_interno"] + "] - Stock: " + df_prod_del["stock"].map('{:,.5f}'.format)
        prod_a_eliminar = st.selectbox("Selecciona el producto a eliminar:", df_prod_del["opcion_eliminar"])
        if prod_a_eliminar:
            idx_d = df_prod_del[df_prod_del["opcion_eliminar"] == prod_a_eliminar].index[0]
            id_producto_borrar = df_prod_del.loc[idx_d, "id"]
            nombre_producto_borrar = df_prod_del.loc[idx_d, "nombre"]
            confirmar_check = st.checkbox(f"Confirmo que deseo marcar como inactivo y poner el stock a 0: '{nombre_producto_borrar}'")
            if st.button("❌ Marcar como Inactivo / Stock a 0", type="primary"):
                if confirmar_check:
                    try:
                        with conn.session as s:
                            s.execute(
                                text("UPDATE productos SET stock = 0, nombre = CONCAT(nombre, ' [INACTIVO]') WHERE id = :p_id"),
                                dict(p_id=int(id_producto_borrar)),
                            )
                            s.commit()
                        st.success(f"✅ El producto '{nombre_producto_borrar}' ha sido desactivado y su stock se puso en 0.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error al actualizar el producto: {e}")
                else:
                    st.warning("Por favor, marca la casilla de confirmación antes de proceder.")
