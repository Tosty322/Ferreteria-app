from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine


# --- CONEXIÓN A SUPABASE ---
def conectar_db():
  # Lee la URL directamente de los Secrets de Streamlit de forma segura
  db_url = st.secrets["connections"]["postgresql"]["url"]
  return create_engine(db_url)


# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Ferretería Sincronizada", layout="wide")

st.title("🛠️ Sistema de Control y Ventas - Ferretería")
st.sidebar.title("Menú de Navegación")

menu = st.sidebar.selectbox(
    "Seleccione una opción",
    [
        "Inventario Actual",
        "Registrar Producto",
        "Registrar Compra / Reposición",
        "Historial de Compras",
        "Actualizar Precios",
        "Historial de Precios",
        "Registrar Venta (POS)",
        "Historial de Ventas",
    ],
)

# -------------------------------------------------------------
# 1. INVENTARIO ACTUAL
# -------------------------------------------------------------
if menu == "Inventario Actual":
  conn = conectar_db()
  st.header("📦 Inventario Actual y Stock Total")

  df_todos = conn.query(
      "SELECT stock, precio_compra, precio_venta FROM productos", ttl=0
  )

  if not df_todos.empty:
    total_items = len(df_todos)
    stock_total_unidades = df_todos["stock"].sum()
    valor_inventario_compra = (
        df_todos["stock"] * df_todos["precio_compra"]
    ).sum()
    valor_inventario_venta = (
        df_todos["stock"] * df_todos["precio_venta"]
    ).sum()

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Variedad de Productos", f"{total_items} ítems")
    col_m2.metric("Stock Total de Unidades", f"{stock_total_unidades:,.2f}")
    col_m3.metric("Valor Inventario (Costo)", f"S/ {valor_inventario_compra:,.2f}")

  st.divider()

  busqueda_inv = st.text_input(
      "🔍 Buscar producto por nombre o código en el inventario:"
  )

  if busqueda_inv:
    query = f"SELECT * FROM productos WHERE nombre ILIKE '%{busqueda_inv}%' OR codigo_interno ILIKE '%{busqueda_inv}%'"
  else:
    query = "SELECT * FROM productos"

  df_productos = conn.query(query, ttl=0)

  if df_productos.empty:
    st.info("No se encontraron productos con ese criterio.")
  else:
    st.dataframe(df_productos, use_container_width=True)

# -------------------------------------------------------------
# 2. REGISTRAR PRODUCTO
# -------------------------------------------------------------
elif menu == "Registrar Producto":
  st.header("➕ Registrar Nuevo Producto")

  with st.form("form_producto"):
    col1, col2 = st.columns(2)
    with col1:
      codigo = st.text_input("Código Interno (Ej: TUB-001)")
      nombre = st.text_input('Nombre del Producto (Ej: Tubo PVC Desagüe 4")')
      categoria = st.selectbox(
          "Categoría",
          [
              "Gasfitería",
              "Electricidad",
              "Construcción",
              "Herramientas",
              "Pinturas",
              "Plásticos",
              "Limpieza",
              "Iluminación",
              "Otros",
          ],
      )
    with col2:
      unidad = st.selectbox(
          "Unidad de Medida",
          ["Unidad", "Docena", "Metro", "Kilo", "Litro", "Caja"],
      )
      stock = st.number_input("Stock Inicial", min_value=0.0, format="%.2f")
      precio_venta = st.number_input(
          "Precio de Venta (S/)", min_value=0.0, format="%.2f"
      )
      precio_compra = st.number_input(
          "Precio de Compra / Costo (S/)", min_value=0.0, format="%.2f"
      )

    submit = st.form_submit_button("Guardar Producto")

    if submit:
      if codigo and nombre:
        try:
          conn = conectar_db()
          with conn.session as s:
            s.execute(
                """
                            INSERT INTO productos (codigo_interno, nombre, categoria, unidad_medida, stock, precio_venta, precio_compra)
                            VALUES (:codigo, :nombre, :categoria, :unidad, :stock, :precio_venta, :precio_compra)
                        """,
                dict(
                    codigo=codigo,
                    nombre=nombre,
                    categoria=categoria,
                    unidad=unidad,
                    stock=stock,
                    precio_venta=precio_venta,
                    precio_compra=precio_compra,
                ),
            )
            s.commit()
          st.success(f"¡Producto '{nombre}' registrado con éxito!")
        except Exception as e:
          st.error(
              f"Error al registrar (es probable que el código '{codigo}' ya"
              f" exista): {e}"
          )
      else:
        st.warning("Completa al menos el código y el nombre.")

# -------------------------------------------------------------
# 3. REGISTRAR COMPRA / REPOSICIÓN
# -------------------------------------------------------------
elif menu == "Registrar Compra / Reposición":
  st.header("📥 Registrar Compra (Aumentar Stock y Actualizar Costos)")
  conn = conectar_db()

  busqueda_compra = st.text_input(
      "🔍 Escribe para filtrar producto (ej: 'tubo', 'cemento'):"
  )

  if busqueda_compra:
    query_compra = f"SELECT id, codigo_interno, nombre, stock, precio_compra, precio_venta, unidad_medida FROM productos WHERE nombre ILIKE '%{busqueda_compra}%' OR codigo_interno ILIKE '%{busqueda_compra}%'"
  else:
    query_compra = "SELECT id, codigo_interno, nombre, stock, precio_compra, precio_venta, unidad_medida FROM productos"

  df_prod_compra = conn.query(query_compra, ttl=0)

  if df_prod_compra.empty:
    st.warning("No se encontró ningún producto con ese criterio.")
  else:
    df_prod_compra["opcion_compra"] = (
        df_prod_compra["nombre"]
        + " [Unidad: "
        + df_prod_compra["unidad_medida"]
        + "] (Stock: "
        + df_prod_compra["stock"].astype(str)
        + " - Cod: "
        + df_prod_compra["codigo_interno"]
        + ")"
    )

    prod_seleccionado = st.selectbox(
        "Selecciona el producto filtrado:", df_prod_compra["opcion_compra"]
    )

    if prod_seleccionado:
      idx = df_prod_compra[
          df_prod_compra["opcion_compra"] == prod_seleccionado
      ].index[0]
      p_id = df_prod_compra.loc[idx, "id"]
      stock_actual = df_prod_compra.loc[idx, "stock"]
      c_actual = df_prod_compra.loc[idx, "precio_compra"]
      v_actual = df_prod_compra.loc[idx, "precio_venta"]
      u_medida = df_prod_compra.loc[idx, "unidad_medida"]

      st.info(
          f"📏 **Unidad de Medida:** {u_medida}  |  📦 **Stock actual:**"
          f" {stock_actual} {u_medida}  |  🏷️ **Precio Compra Anterior:** S/"
          f" {c_actual:.2f}  |  💰 **Precio Venta Anterior:** S/"
          f" {v_actual:.2f}"
      )

      with st.form("form_compra_stock"):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
          cantidad_a_comprar = st.number_input(
              f"Cantidad a sumar al stock ({u_medida})",
              min_value=0.01,
              value=1.00,
              format="%.2f",
          )
          nuevo_precio_compra = st.number_input(
              "Nuevo Precio de Compra / Costo unitario (S/)",
              min_value=0.0,
              value=float(c_actual),
              format="%.2f",
          )
        with col_c2:
          nuevo_precio_venta = st.number_input(
              "Nuevo Precio de Venta (S/)",
              min_value=0.0,
              value=float(v_actual),
              format="%.2f",
          )
          st.write("")
          st.write(
              f"**Costo Total de la Compra:** S/"
              f" {(cantidad_a_comprar * nuevo_precio_compra):.2f}"
          )

        btn_guardar_compra = st.form_submit_button(
            "➕ Registrar Compra y Actualizar Inventario"
        )

        if btn_guardar_compra:
          fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          nuevo_stock_total = stock_actual + cantidad_a_comprar
          costo_total_compra = cantidad_a_comprar * nuevo_precio_compra

          with conn.session as s:
            s.execute(
                """
                            INSERT INTO compras (producto_id, cantidad, precio_compra_anterior, precio_compra_nuevo, precio_venta_anterior, precio_venta_nuevo, costo_total, fecha_hora)
                            VALUES (:p_id, :cant, :p_c_ant, :p_c_nue, :p_v_ant, :p_v_nue, :c_tot, :f_h)
                        """,
                dict(
                    p_id=int(p_id),
                    cant=float(cantidad_a_comprar),
                    p_c_ant=float(c_actual),
                    p_c_nue=float(nuevo_precio_compra),
                    p_v_ant=float(v_actual),
                    p_v_nue=float(nuevo_precio_venta),
                    c_tot=float(costo_total_compra),
                    f_h=fecha_ahora,
                ),
            )

            s.execute(
                """
                            UPDATE productos 
                            SET stock = :n_stock, precio_compra = :n_p_compra, precio_venta = :n_p_venta
                            WHERE id = :p_id
                        """,
                dict(
                    n_stock=float(nuevo_stock_total),
                    n_p_compra=float(nuevo_precio_compra),
                    n_p_venta=float(nuevo_precio_venta),
                    p_id=int(p_id),
                ),
            )

            if nuevo_precio_venta != v_actual:
              s.execute(
                  """
                                INSERT INTO historial_precios (producto_id, precio_anterior, precio_nuevo, fecha_cambio)
                                VALUES (:p_id, :v_ant, :v_nue, :f_h)
                            """,
                  dict(
                      p_id=int(p_id),
                      v_ant=float(v_actual),
                      v_nue=float(nuevo_precio_venta),
                      f_h=fecha_ahora,
                  ),
              )
            s.commit()

          st.success(
              f"🎉 ¡Compra registrada con éxito! Stock actualizado a"
              f" {nuevo_stock_total} {u_medida}."
          )
          st.rerun()

# -------------------------------------------------------------
# 4. HISTORIAL DE COMPRAS
# -------------------------------------------------------------
elif menu == "Historial de Compras":
  st.header("📋 Historial de Compras y Reposiciones")
  conn = conectar_db()
  query_compras = """
        SELECT 
            c.id AS id_compra,
            c.fecha_hora,
            p.codigo_interno,
            p.nombre AS producto,
            c.cantidad,
            p.unidad_medida,
            c.precio_compra_anterior,
            c.precio_compra_nuevo,
            c.precio_venta_anterior,
            c.precio_venta_nuevo,
            c.costo_total
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
        file_name=(
            "historial_compras_"
            f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        ),
        mime="text/csv",
    )

# -------------------------------------------------------------
# 5. ACTUALIZAR PRECIOS
# -------------------------------------------------------------
elif menu == "Actualizar Precios":
  st.header("🔄 Actualizar Precios Independiente")
  conn = conectar_db()
  df_productos = conn.query(
      "SELECT id, codigo_interno, nombre, precio_venta FROM productos", ttl=0
  )

  if df_productos.empty:
    st.info("No hay productos para actualizar.")
  else:
    df_productos["opcion_combo"] = (
        df_productos["nombre"] + " (Cod: " + df_productos["codigo_interno"] + ")"
    )

    producto_seleccionado = st.selectbox(
        "Selecciona el producto a modificar:", df_productos["opcion_combo"]
    )

    if producto_seleccionado:
      idx = df_productos[
          df_productos["opcion_combo"] == producto_seleccionado
      ].index[0]
      prod_id = df_productos.loc[idx, "id"]
      precio_actual = df_productos.loc[idx, "precio_venta"]

      st.write(f"**Precio de venta actual:** S/ {precio_actual:.2f}")
      nuevo_precio = st.number_input(
          "Nuevo Precio de Venta (S/)",
          min_value=0.0,
          value=float(precio_actual),
          format="%.2f",
      )

      if st.button("Guardar Nuevo Precio"):
        if nuevo_precio != precio_actual:
          fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          with conn.session as s:
            s.execute(
                """
                            INSERT INTO historial_precios (producto_id, precio_anterior, precio_nuevo, fecha_cambio)
                            VALUES (:p_id, :p_ant, :p_nue, :f_h)
                        """,
                dict(
                    p_id=int(prod_id),
                    p_ant=float(precio_actual),
                    p_nue=float(nuevo_precio),
                    f_h=fecha_ahora,
                ),
            )
            s.execute(
                "UPDATE productos SET precio_venta = :n_p WHERE id = :p_id",
                dict(n_p=float(nuevo_precio), p_id=int(prod_id)),
            )
            s.commit()
          st.success("¡Precio actualizado y registrado en el historial!")
          st.rerun()
        else:
          st.info("El nuevo precio es idéntico al actual.")

# -------------------------------------------------------------
# 6. HISTORIAL DE PRECIOS
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
# 7. REGISTRAR VENTA (POS)
# -------------------------------------------------------------
elif menu == "Registrar Venta (POS)":
  st.header("🛒 Caja / Punto de Venta")
  conn = conectar_db()

  filtro_pos = st.text_input(
      "🔍 Escribe para filtrar producto (ej: 'cemento', 'clavo'):"
  )

  if filtro_pos:
    query_pos = f"SELECT id, codigo_interno, nombre, stock, precio_venta, unidad_medida FROM productos WHERE nombre ILIKE '%{filtro_pos}%' OR codigo_interno ILIKE '%{filtro_pos}%'"
  else:
    query_pos = (
        "SELECT id, codigo_interno, nombre, stock, precio_venta, unidad_medida"
        " FROM productos"
    )

  df_productos = conn.query(query_pos, ttl=0)

  if df_productos.empty:
    st.warning("No se encontró ningún producto registrado.")
  else:
    if "carrito" not in st.session_state:
      st.session_state.carrito = []

    df_productos["opcion_pos"] = (
        df_productos["nombre"]
        + " ➡️ [Unidad: "
        + df_productos["unidad_medida"]
        + "] | Stock: "
        + df_productos["stock"].astype(str)
        + " | S/ "
        + df_productos["precio_venta"].astype(str)
    )

    col_select, col_cant = st.columns([3, 1])
    with col_select:
      prod_elegido = st.selectbox(
          "Selecciona el producto filtrado:", df_productos["opcion_pos"]
      )
    with col_cant:
      idx_sel = df_productos[
          df_productos["opcion_pos"] == prod_elegido
      ].index[0]
      unidad_sel = df_productos.loc[idx_sel, "unidad_medida"]
      cantidad_vender = st.number_input(
          f"Cantidad ({unidad_sel})",
          min_value=0.01,
          value=1.00,
          format="%.2f",
      )

    if st.button("➕ Agregar al Carrito"):
      p_id = df_productos.loc[idx_sel, "id"]
      p_nombre = df_productos.loc[idx_sel, "nombre"]
      p_stock = df_productos.loc[idx_sel, "stock"]
      p_precio = df_productos.loc[idx_sel, "precio_venta"]

      if cantidad_vender > p_stock:
        st.error(
            f"¡Stock insuficiente! Stock disponible: {p_stock} {unidad_sel}"
        )
      else:
        st.session_state.carrito.append({
            "id": int(p_id),
            "nombre": p_nombre,
            "cantidad": float(cantidad_vender),
            "precio": float(p_precio),
            "subtotal": float(cantidad_vender * p_precio),
        })
        st.success(f"Agregado: {p_nombre} ({cantidad_vender} {unidad_sel})")

    if st.session_state.carrito:
      st.subheader("🛍️ Productos en el Ticket Actual")
      df_carrito = pd.DataFrame(st.session_state.carrito)
      st.dataframe(
          df_carrito[["nombre", "cantidad", "precio", "subtotal"]],
          use_container_width=True,
      )

      total_original = df_carrito["subtotal"].sum()
      st.write(
          f"Subtotal de productos sin descuento: **S/ {total_original:.2f}**"
      )

      st.subheader("🏷️ Ajuste de Precio / Descuento")
      total_venta = st.number_input(
          "Total Final a Cobrar al Cliente (S/):",
          min_value=0.01,
          value=float(total_original),
          format="%.2f",
      )

      st.subheader("💳 Modalidad de Pago")
      metodo_pago = st.selectbox(
          "Forma principal / Tipo",
          [
              "Efectivo",
              "Yape / Plin",
              "Mixto (Yape/Plin + Efectivo)",
              "Tarjeta",
          ],
      )

      monto_yape = 0.0
      monto_efectivo = 0.0

      if metodo_pago == "Mixto (Yape/Plin + Efectivo)":
        col_p1, col_p2 = st.columns(2)
        with col_p1:
          monto_yape = st.number_input(
              "Monto pagado con Yape/Plin (S/)",
              min_value=0.0,
              max_value=float(total_venta),
              value=float(total_venta) / 2,
              format="%.2f",
          )
        with col_p2:
          monto_efectivo = total_venta - monto_yape
          st.write(
              f"Monto automático en Efectivo: **S/ {monto_efectivo:.2f}**"
          )
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
                  """
                                INSERT INTO ventas (fecha_hora, total, metodo_pago, monto_yape, monto_efectivo)
                                VALUES (:f_h, :tot, :m_p, :m_y, :m_e)
                                RETURNING id
                            """,
                  dict(
                      f_h=fecha_venta,
                      tot=float(total_venta),
                      m_p=metodo_pago,
                      m_y=float(monto_yape),
                      m_e=float(monto_efectivo),
                  ),
              )
              venta_id = res.fetchone()[0]

              factor = (
                  total_venta / total_original if total_original > 0 else 1.0
              )

              for item in st.session_state.carrito:
                subtotal_proporcional = item["subtotal"] * factor
                precio_unitario_proporcional = (
                    subtotal_proporcional / item["cantidad"]
                )

                s.execute(
                    """
                                    INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                                    VALUES (:v_id, :p_id, :cant, :p_u, :sub)
                                """,
                    dict(
                        v_id=int(venta_id),
                        p_id=int(item["id"]),
                        cant=float(item["cantidad"]),
                        p_u=float(precio_unitario_proporcional),
                        sub=float(subtotal_proporcional),
                    ),
                )

                s.execute(
                    """
                                    UPDATE productos SET stock = stock - :cant WHERE id = :p_id
                                """,
                    dict(cant=float(item["cantidad"]), p_id=int(item["id"])),
                )

              s.commit()

            st.success(
                f"🎉 ¡Venta registrada con éxito! **N° de Boleta: #{venta_id:04d}**"
            )
            st.session_state.carrito = []
            st.rerun()

          except Exception as e:
            st.error(f"❌ Error al guardar la venta: {e}")

      with col_btn2:
        if st.button("🗑️ Vaciar Carrito"):
          st.session_state.carrito = []
          st.rerun()

# -------------------------------------------------------------
# 8. HISTORIAL DE VENTAS
# -------------------------------------------------------------
elif menu == "Historial de Ventas":
  st.header("📊 Historial de Ventas y Boletas Detallado")
  conn = conectar_db()
  query_historial_completo = """
        SELECT 
            v.id AS n_boleta,
            v.fecha_hora,
            p.nombre AS producto,
            dv.cantidad,
            p.unidad_medida,
            dv.precio_unitario,
            dv.subtotal,
            v.metodo_pago,
            v.monto_yape,
            v.monto_efectivo,
            v.total AS total_boleta
        FROM detalle_ventas dv
        JOIN ventas v ON dv.venta_id = v.id
        JOIN productos p ON dv.producto_id = p.id
        ORDER BY v.id DESC, v.fecha_hora DESC
    """

  df_historial = conn.query(query_historial_completo, ttl=0)

  if df_historial.empty:
    st.info("No hay ventas registradas todavía.")
  else:
    df_historial["n_boleta"] = df_historial["n_boleta"].apply(
        lambda x: f"#{int(x):04d}"
    )
    st.dataframe(df_historial, use_container_width=True)

    csv_data = df_historial.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Descargar Historial Detallado en Excel (CSV)",
        data=csv_data,
        file_name=(
            "historial_ventas_boletas_"
            f"{datetime.now().strftime('%Y-%m-%d')}.csv"
        ),
        mime="text/css",
    )
