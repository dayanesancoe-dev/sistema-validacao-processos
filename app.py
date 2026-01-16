import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date
import sqlite3
import os
from fpdf import FPDF

# ==================== CONFIGURAÇÃO INICIAL ====================
st.set_page_config(page_title="Sistema de Validação", page_icon="🏛️", layout="wide")

# Tentativa segura de importar bibliotecas gráficas
try:
    import pandas as pd
    import plotly.express as px
except ImportError:
    pd = None
    px = None

# ==================== BANCO DE DADOS ====================
@st.cache_resource
def init_db():
    try:
        conn = sqlite3.connect('processos.db', check_same_thread=False)
        c = conn.cursor()
        # Tabelas
        c.execute('''CREATE TABLE IF NOT EXISTS processos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            rt TEXT, requerente TEXT, analista TEXT, uso TEXT,
            tipologia TEXT, area REAL, data_protocolo TEXT,
            status TEXT DEFAULT 'Protocolado',
            data_cadastro TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS tramitacao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER, setor TEXT, data_entrada TEXT,
            data_saida TEXT, observacao TEXT,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processo_id INTEGER, resultado TEXT, status TEXT,
            data_analise TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (processo_id) REFERENCES processos(id)
        )''')
        
        # === CORREÇÃO DE NOMES DE SETORES ANTIGOS ===
        updates = [
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pró-análise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pró-Análise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pro-analise'",
            "UPDATE tramitacao SET setor = 'Pré-análise' WHERE setor = 'Pro-Analise'"
        ]
        for cmd in updates:
            c.execute(cmd)
            
        conn.commit()
        return conn
    except Exception as e:
        st.error(f"Erro no Banco de Dados: {e}")
        return None

conn = init_db()

# ==================== FUNÇÕES AUXILIARES ====================
def executar_query(query, params=(), commit=False):
    if not conn: return False, "Sem conexão"
    try:
        c = conn.cursor()
        c.execute(query, params)
        if commit: conn.commit()
        return True, c
    except Exception as e:
        return False, str(e)

def listar_processos():
    suc, res = executar_query('SELECT * FROM processos ORDER BY id DESC')
    return res.fetchall() if suc else []

def buscar_processo(numero_ou_id):
    query = 'SELECT * FROM processos WHERE id = ?' if isinstance(numero_ou_id, int) else 'SELECT * FROM processos WHERE numero = ?'
    suc, res = executar_query(query, (numero_ou_id,))
    return res.fetchone() if suc else None

def get_processos_df():
    if not conn: return pd.DataFrame()
    try:
        df = pd.read_sql_query("SELECT * FROM processos", conn)
        df['data_protocolo'] = pd.to_datetime(df['data_protocolo'], errors='coerce')
        return df
    except Exception:
        return pd.DataFrame()

# === FUNÇÃO DE GERAÇÃO DE PDF DO DASHBOARD ===
class PDFRelatorio(FPDF):
    def header(self):
        # Fundo do cabeçalho
        self.set_fill_color(240, 240, 240)
        self.rect(0, 0, 210, 30, 'F')
        self.set_font('Arial', 'B', 14)
        self.set_y(10)
        self.cell(0, 10, 'Relatório Gerencial - Sistema de Validação', 0, 1, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()} - Gerado via Sistema Automático', 0, 0, 'C')

def gerar_pdf_dashboard(df, metricas, fig_status=None, fig_uso=None, fig_tipo=None):
    pdf = PDFRelatorio()
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    
    # 1. Cabeçalho com Métricas Gerais
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"Data do Relatório: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1)
    pdf.ln(2)
    
    # Tabela de Resumo Executivo
    pdf.set_fill_color(230, 230, 250) # Lilás bem claro
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, "  Resumo Executivo", 0, 1, 'L', fill=True)
    pdf.ln(2)
    
    pdf.set_font("Arial", size=10)
    w_col = 63
    pdf.cell(w_col, 8, f"Total de Processos: {metricas['total']}", 1)
    pdf.cell(w_col, 8, f"Aprovados: {metricas['aprovados']}", 1)
    pdf.cell(w_col, 8, f"Média Dias: {metricas['media_dias']}", 1, 1)
    pdf.cell(w_col*2, 8, f"Área Total Analisada: {metricas['area_total']}", 1, 1)
    pdf.ln(5)

    # 2. Inserção dos Gráficos
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(230, 230, 250)
    pdf.cell(0, 8, "  Indicadores Visuais", 0, 1, 'L', fill=True)
    pdf.ln(2)
    
    def salvar_img_temp(fig, nome):
        try:
            fig.write_image(nome, width=600, height=400, scale=2)
            return True
        except Exception:
            return False

    y_start = pdf.get_y()
    
    # GRÁFICOS LADO A LADO (Status e Uso)
    if fig_status and fig_uso:
        salvar_img_temp(fig_status, "temp_status.png")
        salvar_img_temp(fig_uso, "temp_uso.png")
        pdf.image("temp_status.png", x=10, y=y_start, w=90)
        pdf.image("temp_uso.png", x=105, y=y_start, w=90)
        if os.path.exists("temp_status.png"): os.remove("temp_status.png")
        if os.path.exists("temp_uso.png"): os.remove("temp_uso.png")
        pdf.ln(65)

    # GRÁFICO DE TIPOLOGIA
    if fig_tipo:
        if pdf.get_y() > 220: pdf.add_page()
        salvar_img_temp(fig_tipo, "temp_tipo.png")
        x_center = (210 - 120) / 2
        pdf.image("temp_tipo.png", x=x_center, w=120)
        if os.path.exists("temp_tipo.png"): os.remove("temp_tipo.png")
        pdf.ln(5)

    # 3. Produtividade Analistas
    if pdf.get_y() > 220: pdf.add_page()
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(230, 230, 250)
    pdf.cell(0, 8, "  Produtividade da Equipe", 0, 1, 'L', fill=True)
    pdf.ln(2)
    
    df_analista = df[df['analista'].str.len() > 0].groupby('analista')['area'].sum().sort_values(ascending=False)
    
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(120, 8, "Analista Responsável", 1, 0, fill=True)
    pdf.cell(50, 8, "Área Total (m²)", 1, 1, fill=True)
    
    pdf.set_font("Arial", size=9)
    for analista, area in df_analista.items():
        analista_clean = str(analista).encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(120, 8, analista_clean, 1)
        pdf.cell(50, 8, f"{area:,.2f}", 1, 1)

    return pdf.output(dest='S').encode('latin-1')

# ==================== INTERFACE PRINCIPAL ====================
def main():
    # --- LOGIN ---
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    
    if not st.session_state['logged_in']:
        st.title("🔐 Login")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                admin_user = st.secrets.get("admin_user", {}).get("username", "admin")
                admin_pass = st.secrets.get("admin_user", {}).get("password", "admin")
                
                if user == admin_user and pwd == admin_pass:
                    st.session_state['logged_in'] = True
                    st.rerun()
                else:
                    st.error("Dados incorretos.")
        return

    # --- MENU LATERAL ---
    st.sidebar.title("🏛️ Menu")
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.rerun()
    st.sidebar.markdown("---")
    
    api_key_input = st.sidebar.text_input("API Key Gemini", type="password")
    if api_key_input:
        genai.configure(api_key=api_key_input)
    
    if genai.__version__ < "0.8.3":
        st.sidebar.error(f"⚠️ Versão IA antiga: {genai.__version__}. Atualize o requirements.txt")

    # === SEÇÃO DE DADOS E BACKUP ===
    st.sidebar.markdown("---")
    st.sidebar.header("💾 Dados e Backup")
    
    if conn and pd is not None:
        with st.sidebar.expander("📥 Exportar Planilhas"):
            df_procs = get_processos_df()
            if not df_procs.empty:
                df_export = df_procs.copy()
                df_export['data_protocolo'] = df_export['data_protocolo'].dt.strftime('%d/%m/%Y')
                
                csv_procs = df_export.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button("📄 Lista de Processos", csv_procs, "processos.csv", "text/csv")
            
            try:
                q_hist = "SELECT p.numero, t.* FROM tramitacao t JOIN processos p ON t.processo_id = p.id"
                df_hist = pd.read_sql_query(q_hist, conn)
                if not df_hist.empty:
                    if 'data_entrada' in df_hist.columns:
                        df_hist['data_entrada'] = pd.to_datetime(df_hist['data_entrada']).dt.strftime('%d/%m/%Y')
                    if 'data_saida' in df_hist.columns:
                        df_hist['data_saida'] = pd.to_datetime(df_hist['data_saida']).dt.strftime('%d/%m/%Y')
                    
                    csv_hist = df_hist.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button("📜 Histórico Completo", csv_hist, "historico.csv", "text/csv")
            except: pass
            
        if os.path.exists("processos.db"):
            with open("processos.db", "rb") as f:
                st.sidebar.download_button(
                    label="📦 Baixar Backup (.db)",
                    data=f,
                    file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    mime="application/octet-stream"
                )
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚠️ Restaurar Backup")
        uploaded_db = st.sidebar.file_uploader("Upload do arquivo .db", type="db")
        if uploaded_db:
            st.sidebar.warning("Isso substituirá TODOS os dados.")
            if st.sidebar.button("🔴 Confirmar Restauração"):
                try:
                    with open("processos.db", "wb") as f:
                        f.write(uploaded_db.getbuffer())
                    st.toast("Restaurado com sucesso! Reiniciando...", icon="✅")
                    import time
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.sidebar.error(f"Erro: {e}")

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA", "📈 Dashboard"])

    # === LISTAS GLOBAIS ===
    usos = ["Multifamiliar", "Serviços", "Comércio Varejista", "Indústria", "Unifamiliar", "Misto", "Sem destinação específica"]
    tipos = ["Aprovação inicial", "Levantamento do existente", "Modificação de projeto", "Regularização", "Misto", "Análise RIU", "ERB"]
    setores = ["Análise prévia", "Pré-análise", "Analista", "Parecer externo", "Fiscalização", "Emissão de documentos", "Requerente"]

    # --- ABA 1: CADASTRAR ---
    with tab1:
        st.header("Cadastrar Processo")
        with st.form("novo_proc"):
            c1, c2 = st.columns(2)
            num = c1.text_input("Número Processo")
            rt = c1.text_input("RT")
            uso = c1.selectbox("Uso", usos)
            area = c1.number_input("Área (m²)", min_value=0.0)
            req = c2.text_input("Requerente")
            ana = c2.text_input("Analista")
            tipo = c2.selectbox("Tipo", tipos)
            data = c2.date_input("Data Protocolo", format="DD/MM/YYYY")
            
            if st.form_submit_button("Salvar Processo"):
                suc, msg = executar_query(
                    'INSERT INTO processos (numero, rt, requerente, analista, uso, tipologia, area, data_protocolo) VALUES (?,?,?,?,?,?,?,?)',
                    (num, rt, req, ana, uso, tipo, area, data.strftime('%Y-%m-%d')), commit=True
                )
                if suc: st.success("Sucesso!"); st.rerun()
                else: st.error(f"Erro: {msg}")

    # --- ABA 2: GERENCIAR ---
    with tab2:
        st.header("Editar ou Excluir")
        procs = listar_processos()
        if procs:
            lista_analistas = sorted(list(set([p[4] for p in procs if p[4]])))
            lista_status = sorted(list(set([p[9] for p in procs if p[9]])))
            
            st.caption("Filtros:")
            col_f1, col_f2, col_vazia = st.columns([1, 1, 2])
            with col_f1: filtro_analista = st.selectbox("👤 Analista:", ["Todos"] + lista_analistas)
            with col_f2: filtro_status = st.selectbox("📌 Status:", ["Todos"] + lista_status)
            
            procs_filtrados = procs
            if filtro_analista != "Todos": procs_filtrados = [p for p in procs_filtrados if p[4] == filtro_analista]
            if filtro_status != "Todos": procs_filtrados = [p for p in procs_filtrados if p[9] == filtro_status]

            if procs_filtrados:
                opcoes = {f"{p[1]} - {p[3]} [{p[9]}]": p[0] for p in procs_filtrados}
                sel = st.selectbox("Selecione o Processo:", list(opcoes.keys()))
                pid = opcoes[sel]
                d = buscar_processo(pid)
                
                if d:
                    st.markdown("---")
                    with st.form(f"edit_{pid}"):
                        c1, c2 = st.columns(2)
                        enum = c1.text_input("Número", d[1])
                        ert = c1.text_input("RT", d[2])
                        euso = c1.selectbox("Uso", usos, index=usos.index(d[5]) if d[5] in usos else 0)
                        earea = c1.number_input("Área", float(d[7]))
                        ereq = c2.text_input("Requerente", d[3])
                        eana = c2.text_input("Analista", d[4])
                        etipo = c2.selectbox("Tipo", tipos, index=tipos.index(d[6]) if d[6] in tipos else 0)
                        edata = c2.date_input("Data", datetime.strptime(d[8], '%Y-%m-%d').date(), format="DD/MM/YYYY")
                        
                        status_atuais = ['Protocolado', 'Em Análise', 'Aguardando Correções', 'Aprovado', 'Reprovado']
                        if d[9] not in status_atuais: status_atuais.append(d[9])
                        estatus = c1.selectbox("Status Atual", status_atuais, index=status_atuais.index(d[9]))

                        st.markdown("---")
                        btn_save = st.form_submit_button("💾 Salvar Alterações", type="primary")
                        btn_del = st.form_submit_button("🗑️ Deletar Processo", type="secondary")
                        
                        if btn_save:
                            executar_query('UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=?, status=? WHERE id=?',
                                        (enum, ert, ereq, eana, euso, etipo, earea, edata.strftime('%Y-%m-%d'), estatus, pid), commit=True)
                            st.success("Salvo!"); st.rerun()
                        
                        if btn_del:
                            st.session_state[f'del_{pid}'] = True
                    
                    if st.session_state.get(f'del_{pid}'):
                        st.warning("Confirma a exclusão?")
                        if st.button("Sim, Excluir Definitivamente"):
                            executar_query('DELETE FROM tramitacao WHERE processo_id=?', (pid,), commit=True)
                            executar_query('DELETE FROM analises WHERE processo_id=?', (pid,), commit=True)
                            executar_query('DELETE FROM processos WHERE id=?', (pid,), commit=True)
                            st.success("Excluído!"); st.rerun()
            else:
                st.warning("Nenhum processo encontrado com esses filtros.")

    # --- ABA 3: TRAMITAÇÃO ---
    with tab3:
        st.header("Tramitação")
        if procs:
            opcoes_geral = {f"{p[1]} - {p[3]}": p[0] for p in procs}
            sel_key = st.selectbox("Processo:", list(opcoes_geral.keys()), key="tram_sel_main")
            pid_tram = opcoes_geral[sel_key]
            
            with st.form("new_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                setor = c1.selectbox("Setor Destino", setores)
                obs = c2.text_area("Observação", height=68)
                
                st.markdown("**Datas:**")
                c3, c4 = st.columns(2)
                with c3: dt_ent = st.date_input("📅 Data de Entrada", value=date.today(), format="DD/MM/YYYY")
                with c4:
                    tem_saida = st.checkbox("Informar Data de Saída?")
                    if tem_saida: dt_sai = st.date_input("📅 Data de Saída", value=date.today(), format="DD/MM/YYYY")
                    else: dt_sai = None; st.caption("Saída 'Em Aberto' (Atual)")
                
                st.markdown("---")
                if st.form_submit_button("Movimentar", type="primary"):
                    if not tem_saida:
                        executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL",
                                    (dt_ent.strftime('%Y-%m-%d'), pid_tram), commit=True)
                    
                    saida_val = dt_sai.strftime('%Y-%m-%d') if tem_saida and dt_sai else None
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)",
                                (pid_tram, setor, dt_ent.strftime('%Y-%m-%d'), saida_val, obs), commit=True)
                    st.success("Movimentação registrada!"); st.rerun()
            
            st.divider()
            suc, res = executar_query("SELECT * FROM tramitacao WHERE processo_id=?", (pid_tram,))
            if suc:
                rows = res.fetchall()
                if rows:
                    df = pd.DataFrame(rows, columns=['ID', 'PID', 'Setor', 'Entrada', 'Saída', 'Obs'])
                    df['Setor'] = df['Setor'].replace({'Pró-análise': 'Pré-análise', 'Pró-Análise': 'Pré-análise', 'Pro-analise': 'Pré-análise'})
                    df['Entrada'] = pd.to_datetime(df['Entrada'])
                    df['Saída'] = pd.to_datetime(df['Saída'])
                    
                    now = pd.Timestamp.now().normalize()
                    df['Dias'] = df.apply(lambda x: ((x['Saída'] if pd.notnull(x['Saída']) else now) - x['Entrada']).days, axis=1)
                    
                    st.subheader("📊 Total de Dias por Setor")
                    df_resumo = df.groupby('Setor')['Dias'].sum().reset_index().sort_values('Dias', ascending=False)
                    st.dataframe(df_resumo, use_container_width=True)
                    
                    st.subheader("📜 Histórico Detalhado")
                    df_show = df.sort_values(by='Entrada', ascending=True).copy()
                    df_show['Entrada'] = df_show['Entrada'].dt.strftime('%d/%m/%Y')
                    df_show['Saída'] = df_show['Saída'].dt.strftime('%d/%m/%Y').fillna("Atual")
                    st.dataframe(df_show[['Setor', 'Entrada', 'Saída', 'Dias', 'Obs']], use_container_width=True)

                    st.divider()
                    st.subheader("📝 Editar Histórico")
                    opts_t = {f"{r[2]} ({pd.to_datetime(r[3]).strftime('%d/%m/%Y')})": r[0] for r in rows}
                    sel_t = st.selectbox("Selecione para corrigir:", ["Selecione..."] + list(opts_t.keys()))
                    
                    if sel_t != "Selecione...":
                        tid = opts_t[sel_t]
                        r = next((x for x in rows if x[0] == tid), None)
                        if r:
                            with st.form(f"edit_tram_{tid}"):
                                ec1, ec2 = st.columns(2)
                                idx_setor = setores.index(r[2]) if r[2] in setores else 0
                                esetor = ec1.selectbox("Setor", setores, index=idx_setor)
                                eobs = ec2.text_input("Observação", r[5] or "")
                                ec3, ec4 = st.columns(2)
                                with ec3: edtent = st.date_input("Data Entrada", datetime.strptime(r[3], '%Y-%m-%d').date(), format="DD/MM/YYYY")
                                with ec4:
                                    has_exit = st.checkbox("Possui Saída?", value=bool(r[4]))
                                    edtsai = None
                                    if has_exit:
                                        val_sai = datetime.strptime(r[4], '%Y-%m-%d').date() if r[4] else date.today()
                                        edtsai = st.date_input("Data Saída", val_sai, format="DD/MM/YYYY")
                                
                                st.markdown("---")
                                btn_t_save = st.form_submit_button("Salvar Correção", type="primary")
                                btn_t_del = st.form_submit_button("Excluir Movimentação")
                                
                                if btn_t_save:
                                    s_val = edtsai.strftime('%Y-%m-%d') if has_exit and edtsai else None
                                    executar_query("UPDATE tramitacao SET setor=?, data_entrada=?, data_saida=?, observacao=? WHERE id=?",
                                                (esetor, edtent.strftime('%Y-%m-%d'), s_val, eobs, tid), commit=True)
                                    st.success("Atualizado!"); st.rerun()
                                if btn_t_del:
                                    executar_query("DELETE FROM tramitacao WHERE id=?", (tid,), commit=True)
                                    st.success("Apagado!"); st.rerun()

    # --- ABA 4: KANBAN ---
    with tab4:
        st.header("Kanban")
        cols = st.columns(5)
        stats = ['Protocolado', 'Em Análise', 'Aguardando Correções', 'Aprovado', 'Reprovado']
        for i, s in enumerate(stats):
            with cols[i]:
                st.caption(f"**{s}**")
                for p in [x for x in procs if x[9] == s]:
                    with st.container(border=True):
                        st.write(f"**{p[1]}**\n{p[3]}")
                        col_back, col_next = st.columns(2)
                        if i > 0:
                            if col_back.button("⬅️", key=f"back_{p[0]}"):
                                executar_query("UPDATE processos SET status=? WHERE id=?", (stats[i-1], p[0]), commit=True)
                                st.rerun()
                        if i < 4:
                            if col_next.button("➡️", key=f"next_{p[0]}"):
                                executar_query("UPDATE processos SET status=? WHERE id=?", (stats[i+1], p[0]), commit=True)
                                st.rerun()

    # --- ABA 5: IA ---
    with tab5:
        st.header("Análise IA")
        if not api_key_input and "GOOGLE_API_KEY" not in os.environ: st.info("Insira a API Key no menu lateral para usar a IA.")
        elif procs:
            opcoes_ia = {f"{p[1]} - {p[3]}": p[0] for p in procs}
            sel_ia = st.selectbox("Processo:", list(opcoes_ia.keys()), key="ia_sel")
            pid_ia = opcoes_ia[sel_ia]
            d_ia = buscar_processo(pid_ia)
            up_p = st.file_uploader("Projeto (PDF)", type='pdf', accept_multiple_files=True)
            up_l = st.file_uploader("Lei (PDF)", type='pdf', accept_multiple_files=True)
            if st.button("Analisar") and up_p and up_l:
                with st.spinner("Analisando..."):
                    try:
                        txt_p = ""; txt_l = ""
                        for p_file in up_p:
                            for page in PyPDF2.PdfReader(p_file).pages: txt_p += page.extract_text() or ""
                        for l_file in up_l:
                            for page in PyPDF2.PdfReader(l_file).pages: txt_l += page.extract_text() or ""
                        model = genai.GenerativeModel('models/gemini-1.5-flash')
                        res = model.generate_content(f"Analise se o projeto cumpre a legislação.\nDADOS: {d_ia[3]}, {d_ia[5]}, {d_ia[7]}m²\nLEI: {txt_l[:30000]}\nPROJETO: {txt_p[:30000]}")
                        st.success("Análise realizada!"); st.markdown(res.text)
                    except Exception as e: st.error(f"Erro: {e}")

    # --- ABA 6: DASHBOARD ---
    with tab6:
        st.header("Dashboard")
        if pd is not None and px is not None:
            df = get_processos_df()
            if not df.empty:
                # --- NORMALIZAÇÃO DE DADOS (CORREÇÃO DE DUPLICIDADE) ---
                df['tipologia'] = df['tipologia'].astype(str).str.strip().str.title()
                df['uso'] = df['uso'].astype(str).str.strip().str.title()
                # AQUI ESTÁ A CORREÇÃO DO NOME DO ANALISTA:
                df['analista'] = df['analista'].astype(str).str.strip().str.title()

                c1, c2, c3, c4 = st.columns(4)
                total_processos = len(df)
                area_total = f"{df['area'].sum():,.0f} m²"
                total_aprovados = len(df[df['status']=='Aprovado'])
                media_dias = (pd.Timestamp.now() - df['data_protocolo']).dt.days.mean()
                c1.metric("Total", total_processos); c2.metric("Área Total", area_total)
                c3.metric("Aprovados", total_aprovados); c4.metric("Média Dias", f"{media_dias:.0f}")
                
                fig_status = px.pie(df, names='status', title='Distribuição por Status', color_discrete_sequence=px.colors.qualitative.Set2)
                fig_status.update_layout(template="plotly_white", title_font_size=16)
                
                count_uso = df['uso'].value_counts().reset_index()
                count_uso.columns = ['uso', 'count']
                fig_uso = px.bar(count_uso, x='count', y='uso', orientation='h', title='Uso Principal', color='uso', color_discrete_sequence=px.colors.qualitative.Prism)
                fig_uso.update_layout(template="plotly_white", showlegend=False)
                
                count_tipo = df['tipologia'].value_counts().reset_index()
                count_tipo.columns = ['tipologia', 'count']
                fig_tipo = px.bar(count_tipo, x='count', y='tipologia', orientation='h', title='Tipologia dos Projetos', color='tipologia', color_discrete_sequence=px.colors.qualitative.Bold)
                fig_tipo.update_layout(template="plotly_white", showlegend=False)

                st.divider()
                col_btn, col_vazia = st.columns([1, 4])
                with col_btn:
                    try:
                        metricas_pdf = {'total': total_processos, 'area_total': area_total, 'aprovados': total_aprovados, 'media_dias': f"{media_dias:.0f}"}
                        pdf_bytes = gerar_pdf_dashboard(df, metricas_pdf, fig_status, fig_uso, fig_tipo)
                        st.download_button("📄 Baixar Relatório Colorido", data=pdf_bytes, file_name=f"Relatorio_{datetime.now().strftime('%d-%m-%Y')}.pdf", mime="application/pdf", type="primary")
                    except Exception as e: st.error(f"Erro PDF: {e}")
                st.divider()

                r1, r2 = st.columns(2); r3, r4 = st.columns(2)
                with r1: st.plotly_chart(fig_status, use_container_width=True)
                with r2: st.plotly_chart(fig_uso, use_container_width=True)
                with r3: st.plotly_chart(fig_tipo, use_container_width=True)
                with r4:
                    try:
                        df_tram = pd.read_sql_query("SELECT * FROM tramitacao", conn)
                        if not df_tram.empty:
                            df_tram['data_saida'] = pd.to_datetime(df_tram['data_saida']).fillna(pd.Timestamp.now().normalize())
                            df_tram['dias'] = (df_tram['data_saida'] - pd.to_datetime(df_tram['data_entrada'])).dt.days
                            st.plotly_chart(px.pie(df_tram.groupby('setor')['dias'].sum().reset_index(), values='dias', names='setor', title='Tempo Total (Dias)', color_discrete_sequence=px.colors.qualitative.Safe), use_container_width=True)
                    except: pass
                
                st.divider(); st.subheader("Produtividade da Equipe")
                df_analista = df[df['analista'].str.len() > 0].groupby('analista')['area'].sum().reset_index().sort_values('area', ascending=True)
                if not df_analista.empty:
                    st.plotly_chart(px.bar(df_analista, x='area', y='analista', orientation='h', title='Total de m² Analisados por Analista', text_auto='.0f', labels={'area': 'Área (m²)', 'analista': 'Analista'}), use_container_width=True)

if __name__ == "__main__":
    main()
