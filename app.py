import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime, date
import sqlite3
import os

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
        
        # === CORREÇÃO FORÇADA DE NOMES DE SETORES ANTIGOS ===
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
    api_key = st.sidebar.text_input("API Key Gemini", type="password")
    if api_key: genai.configure(api_key=api_key)

    # === SEÇÃO DE DADOS E BACKUP (BARRA LATERAL) ===
    st.sidebar.markdown("---")
    st.sidebar.header("💾 Dados e Backup")
    
    if conn and pd is not None:
        # 1. Exportar Excel/CSV
        with st.sidebar.expander("📥 Exportar Planilhas"):
            df_procs = get_processos_df()
            if not df_procs.empty:
                csv_procs = df_procs.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button("📄 Lista de Processos", csv_procs, "processos.csv", "text/csv")
            
            try:
                q_hist = "SELECT p.numero, t.* FROM tramitacao t JOIN processos p ON t.processo_id = p.id"
                df_hist = pd.read_sql_query(q_hist, conn)
                if not df_hist.empty:
                    csv_hist = df_hist.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button("📜 Histórico Completo", csv_hist, "historico.csv", "text/csv")
            except: pass

        # 2. Backup do Arquivo .DB
        if os.path.exists("processos.db"):
            with open("processos.db", "rb") as f:
                st.sidebar.download_button(
                    label="📦 Baixar Backup (.db)",
                    data=f,
                    file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                    mime="application/octet-stream",
                    help="Guarde este arquivo. Ele contém TODOS os seus dados."
                )

    # --- ABAS ---
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["➕ Novo", "📝 Gerenciar", "🔄 Tramitação", "📊 Kanban", "🤖 IA", "📈 Dashboard"])

    # Variáveis Globais
    usos = ["Unifamiliar", "Multifamiliar", "Comercial", "Misto", "Industrial", "Institucional"]
    tipos = ["Aprovação Inicial", "Regularização", "Modificação", "Habite-se"]
    
    # === AQUI ESTAVA O ERRO, AGORA ESTÁ CORRIGIDO ===
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
            data = c2.date_input("Data Protocolo")
            
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
            opcoes = {f"{p[1]} - {p[3]}": p[0] for p in procs}
            sel = st.selectbox("Selecione:", list(opcoes.keys()))
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
                    edata = c2.date_input("Data", datetime.strptime(d[8], '%Y-%m-%d').date())
                    
                    st.markdown("---")
                    btn_save = st.form_submit_button("💾 Salvar Alterações", type="primary")
                    btn_del = st.form_submit_button("🗑️ Deletar Processo", type="secondary")

                    if btn_save:
                        executar_query('UPDATE processos SET numero=?, rt=?, requerente=?, analista=?, uso=?, tipologia=?, area=?, data_protocolo=? WHERE id=?',
                                     (enum, ert, ereq, eana, euso, etipo, earea, edata.strftime('%Y-%m-%d'), pid), commit=True)
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

    # --- ABA 3: TRAMITAÇÃO ---
    with tab3:
        st.header("Tramitação")
        if procs:
            sel_key = st.selectbox("Processo:", list(opcoes.keys()), key="tram_sel")
            pid_tram = opcoes[sel_key]
            
            # --- NOVA MOVIMENTAÇÃO ---
            with st.form("new_tram"):
                st.subheader("Nova Movimentação")
                c1, c2 = st.columns(2)
                setor = c1.selectbox("Setor Destino", setores)
                obs = c2.text_area("Observação", height=68)

                st.markdown("**Datas:**")
                c3, c4 = st.columns(2)
                with c3:
                    dt_ent = st.date_input("📅 Data de Entrada", value=date.today())
                with c4:
                    tem_saida = st.checkbox("Informar Data de Saída?")
                    if tem_saida:
                        dt_sai = st.date_input("📅 Data de Saída", value=date.today())
                    else:
                        dt_sai = None
                        st.caption("Saída 'Em Aberto' (Atual)")
                
                st.markdown("---")
                if st.form_submit_button("Movimentar", type="primary"):
                    if not tem_saida:
                        executar_query("UPDATE tramitacao SET data_saida=? WHERE processo_id=? AND data_saida IS NULL", 
                                     (dt_ent.strftime('%Y-%m-%d'), pid_tram), commit=True)
                    
                    saida_val = dt_sai.strftime('%Y-%m-%d') if tem_saida and dt_sai else None
                    executar_query("INSERT INTO tramitacao (processo_id, setor, data_entrada, data_saida, observacao) VALUES (?,?,?,?,?)",
                                 (pid_tram, setor, dt_ent.strftime('%Y-%m-%d'), saida_val, obs), commit=True)
                    st.success("Movimentação registrada!")
                    st.rerun()

            # --- HISTÓRICO ---
            st.divider()
            suc, res = executar_query("SELECT * FROM tramitacao WHERE processo_id=? ORDER BY data_entrada DESC", (pid_tram,))
            if suc:
                rows = res.fetchall()
                if rows:
                    df = pd.DataFrame(rows, columns=['ID', 'PID', 'Setor', 'Entrada', 'Saída', 'Obs'])
                    df['Setor'] = df['Setor'].replace({'Pró-análise': 'Pré-análise', 'Pró-Análise': 'Pré-análise', 'Pro-analise': 'Pré-análise'})
                    df['Entrada'] = pd.to_datetime(df['Entrada'])
                    df['Saída'] = pd.to_datetime(df['Saída'])
                    now = pd.Timestamp.now().normalize()
                    df['Dias'] = df.apply(lambda x: ((x['Saída'] if pd.notnull(x['Saída']) else now) - x['Entrada']).days, axis=1)
                    
                    # Resumo
                    st.subheader("📊 Total de Dias por Setor")
                    df_resumo = df.groupby('Setor')['Dias'].sum().reset_index().sort_values('Dias', ascending=False)
                    st.dataframe(df_resumo, use_container_width=True)
                    
                    # Detalhado
                    st.subheader("📜 Histórico Detalhado")
                    df_show = df.copy()
                    df_show['Entrada'] = df_show['Entrada'].dt.strftime('%d/%m/%Y')
                    df_show['Saída'] = df_show['Saída'].dt.strftime('%d/%m/%Y').fillna("Atual")
                    st.dataframe(df_show[['Setor', 'Entrada', 'Saída', 'Dias', 'Obs']], use_container_width=True)
                    
                    # --- EDIÇÃO ---
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
                                cur_sector = r[2]
                                if cur_sector in ['Pró-análise', 'Pró-Análise']: cur_sector = 'Pré-análise'
                                idx_setor = setores.index(cur_sector) if cur_sector in setores else 0
                                esetor = ec1.selectbox("Setor", setores, index=idx_setor)
                                eobs = ec2.text_input("Observação", r[5] or "")
                                
                                st.markdown("**Datas:**")
                                ec3, ec4 = st.columns(2)
                                with ec3:
                                    edtent = st.date_input("Data Entrada", datetime.strptime(r[3], '%Y-%m-%d').date())
                                with ec4:
                                    has_exit = st.checkbox("Possui Saída?", value=bool(r[4]))
                                    edtsai = None
                                    if has_exit:
                                        val_sai = datetime.strptime(r[4], '%Y-%m-%d').date() if r[4] else date.today()
                                        edtsai = st.date_input("Data Saída", val_sai)
                                
                                st.markdown("---")
                                btn_t_save = st.form_submit_button("Salvar Correção", type="primary")
                                btn_t_del = st.form_submit_button("Excluir Movimentação")
                                
                                if btn_t_save:
                                    s_val = edtsai.strftime('%Y-%m-%d') if has_exit and edtsai else None
                                    executar_query("UPDATE tramitacao SET setor=?, data_entrada=?, data_saida=?, observacao=? WHERE id=?",
                                                 (esetor, edtent.strftime('%Y-%m-%d'), s_val, eobs, tid), commit=True)
                                    st.success("Atualizado!")
                                    st.rerun()
                                if btn_t_del:
                                    executar_query("DELETE FROM tramitacao WHERE id=?", (tid,), commit=True)
                                    st.success("Apagado!")
                                    st.rerun()

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
                        if i < 4:
                            if st.button("➡️", key=f"k_{p[0]}"):
                                executar_query("UPDATE processos SET status=? WHERE id=?", (stats[i+1], p[0]), commit=True)
                                st.rerun()

    # --- ABA 5: IA (PRIORIDADE PRO) ---
    with tab5:
        st.header("Análise IA")
        if not api_key: st.warning("Sem API Key.")
        elif procs:
            pid_ia = opcoes[st.selectbox("Processo:", list(opcoes.keys()), key="ia_sel")]
            d_ia = buscar_processo(pid_ia)
            
            up_p = st.file_uploader("Projeto (PDF)", type='pdf', accept_multiple_files=True)
            up_l = st.file_uploader("Lei (PDF)", type='pdf', accept_multiple_files=True)
            
            if st.button("Analisar") and up_p and up_l:
                with st.spinner("Analisando..."):
                    try:
                        txt_p = ""
                        for p_file in up_p:
                            reader = PyPDF2.PdfReader(p_file)
                            for page in reader.pages: txt_p += page.extract_text() or ""
                        
                        txt_l = ""
                        for l_file in up_l:
                            reader = PyPDF2.PdfReader(l_file)
                            for page in reader.pages: txt_l += page.extract_text() or ""
                        
                        # PRIORIZA O MODELO PRO (MELHOR RACIOCÍNIO)
                        modelos = [
                            'gemini-1.5-pro',        # Tenta o PRO primeiro
                            'models/gemini-1.5-pro',
                            'gemini-2.0-flash',      # Fallback para o Flash 2.0 (Muito rápido)
                            'models/gemini-2.0-flash',
                            'gemini-1.5-flash'       # Fallback final
                        ]
                        
                        resultado = None
                        
                        for m_nome in modelos:
                            try:
                                model = genai.GenerativeModel(m_nome)
                                resultado = model.generate_content(f"""
                                Você é um analista experiente. Analise se o projeto cumpre a legislação.
                                DADOS: {d_ia[3]}, {d_ia[5]}, {d_ia[7]}m²
                                LEI: {txt_l[:20000]}
                                PROJETO: {txt_p[:20000]}
                                Responda com: 1. Resumo, 2. Conformidade, 3. Desacordo, 4. Conclusão.
                                """)
                                st.success(f"Análise feita com: {m_nome}")
                                break
                            except: continue
                        
                        if resultado:
                            st.markdown(resultado.text)
                        else:
                            st.error("Erro na conexão com IA. Verifique API Key e requirements.txt")
                            with st.expander("Debug"):
                                try:
                                    for m in genai.list_models(): st.write(m.name)
                                except Exception as e: st.write(e)

                    except Exception as e: st.error(f"Erro geral: {e}")

    # --- ABA 6: DASHBOARD ---
    with tab6:
        st.header("Dashboard")
        if pd is not None and px is not None:
            df = get_processos_df()
            if not df.empty:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Total", len(df))
                c2.metric("Área Total", f"{df['area'].sum():,.0f} m²")
                c3.metric("Aprovados", len(df[df['status']=='Aprovado']))
                dias = (pd.Timestamp.now() - df['data_protocolo']).dt.days.mean()
                c4.metric("Média Dias", f"{dias:.0f}")
                
                st.divider()
                g1, g2 = st.columns(2)
                g1.plotly_chart(px.pie(df, names='status', title='Status'), use_container_width=True)
                g2.plotly_chart(px.bar(df['uso'].value_counts().reset_index(), x='count', y='uso', orientation='h', title='Uso'), use_container_width=True)

if __name__ == "__main__":
    main()
