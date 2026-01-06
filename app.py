import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime

st.set_page_config(page_title="Validação de Projetos", page_icon="🏛️", layout="wide")

st.title("🏛️ Sistema de Validação de Projetos")
st.markdown("**Prefeitura de Contagem** — Análise com Google Gemini")

# Configuração API
st.header("⚙️ Configuração")
api_key = st.text_input("Cole sua API Key do Google Gemini:", type="password")

if api_key:
    try:
        genai.configure(api_key=api_key)
        st.success("✅ API configurada!")

        # Descobrir modelos disponíveis
        if 'modelo_selecionado' not in st.session_state:
            with st.spinner("🔍 Detectando modelos disponíveis..."):
                modelos_disponiveis = []
                try:
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            modelos_disponiveis.append(m.name)

                    if modelos_disponiveis:
                        st.session_state.modelo_selecionado = modelos_disponiveis[0]
                        st.info(f"✅ Modelo detectado: {st.session_state.modelo_selecionado}")
                    else:
                        st.error("❌ Nenhum modelo disponível. Gere uma nova API Key em: https://aistudio.google.com/app/apikey")
                        st.stop()
                except Exception as e:
                    st.error(f"❌ Erro ao listar modelos: {str(e)}")
                    st.info("Tentando modelo padrão...")
                    st.session_state.modelo_selecionado = "gemini-1.5-flash"

        st.divider()
        st.header("📄 Upload de Documentos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📐 PDFs do Projeto")
            projetos = st.file_uploader("Anexe os PDFs", type=['pdf'], accept_multiple_files=True, key="proj")
            if projetos:
                st.success(f"✅ {len(projetos)} arquivo(s)")

        with col2:
            st.subheader("📜 PDFs da Legislação")
            legislacoes = st.file_uploader("Anexe os PDFs", type=['pdf'], accept_multiple_files=True, key="leg")
            if legislacoes:
                st.success(f"✅ {len(legislacoes)} arquivo(s)")

        st.divider()
        st.header("📋 Dados do Processo")

        col1, col2, col3 = st.columns(3)

        with col1:
            numero = st.text_input("Número", placeholder="Ex: 018.11103/2025")
        with col2:
            requerente = st.text_input("Requerente", placeholder="Nome completo")
        with col3:
            area = st.number_input("Área (m²)", min_value=0.0, step=0.1, value=220.0)

        st.divider()
        st.subheader("📏 Regras a Verificar")
        regras = st.text_area(
            "Digite as regras (uma por linha):", 
            height=150,
            value="Verificar de acordo com a 393/2025",
            placeholder="Ex:\nArt. 10 - Área mínima 50m²"
        )

        st.divider()

        if st.button("🔍 ANALISAR COM IA", type="primary", use_container_width=True):
            if projetos and legislacoes and numero and requerente and regras:
                with st.spinner("🤖 Analisando projeto..."):
                    try:
                        # Extrair textos
                        texto_proj = ""
                        for idx, pdf in enumerate(projetos, 1):
                            reader = PyPDF2.PdfReader(pdf)
                            for pag in reader.pages:
                                texto_proj += pag.extract_text() + "\n"

                        texto_leg = ""
                        for idx, pdf in enumerate(legislacoes, 1):
                            reader = PyPDF2.PdfReader(pdf)
                            for pag in reader.pages:
                                texto_leg += pag.extract_text() + "\n"

                        # Criar modelo
                        model = genai.GenerativeModel(st.session_state.modelo_selecionado)

                        # Prompt
                        prompt = f"""Você é analista técnico da Prefeitura de Contagem especializado em análise de projetos arquitetônicos.

**DADOS DO PROCESSO:**
- Número: {numero}
- Requerente: {requerente}
- Área: {area}m²

**LEGISLAÇÃO MUNICIPAL:**
{texto_leg[:5000]}

**REGRAS A VERIFICAR:**
{regras}

**PROJETO SUBMETIDO:**
{texto_proj[:7000]}

**IMPORTANTE:** SEMPRE cite o artigo específico da legislação. NÃO use informações fora da lei fornecida.

Analise detalhadamente e responda:

## ✅ CONFORMIDADES
Liste o que está de acordo, citando o artigo específico da lei.

## ❌ NÃO CONFORMIDADES - PONTOS A CORRIGIR
Para cada violação encontrada:
- **Artigo violado:** (número e texto completo do artigo)
- **Problema encontrado:** (descrição técnica)
- **Localização no projeto:** (onde está o problema)
- **Correção necessária:** (o que precisa ser feito)

## ⚠️ PONTOS DE ATENÇÃO
Itens que precisam verificação adicional ou documentação complementar.

## 🔧 RECOMENDAÇÕES TÉCNICAS
Sugestões detalhadas para correção.

## 📊 PARECER TÉCNICO FINAL
**APROVADO** ou **REPROVADO**

Justifique citando APENAS os artigos da legislação fornecida.
"""

                        response = model.generate_content(prompt)

                        st.divider()
                        st.header("📋 RELATÓRIO DE ANÁLISE")

                        texto_resp = response.text.upper()
                        if "APROVADO" in texto_resp and "REPROVADO" not in texto_resp:
                            st.success("✅ PROJETO APROVADO")
                        elif "REPROVADO" in texto_resp:
                            st.error("❌ PROJETO REPROVADO")

                        st.markdown(response.text)

                        # Relatório para download
                        relatorio = f"""PREFEITURA DE CONTAGEM - MG
RELATÓRIO DE ANÁLISE DE PROJETO ARQUITETÔNICO

Processo: {numero}
Requerente: {requerente}
Área: {area}m²
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
Modelo IA: {st.session_state.modelo_selecionado}

{'='*80}

{response.text}

{'='*80}
Relatório gerado por IA - Prefeitura de Contagem
Sistema de Validação de Projetos
"""

                        st.divider()
                        st.download_button(
                            "📥 BAIXAR RELATÓRIO COMPLETO",
                            relatorio,
                            f"relatorio_{numero.replace('.', '_').replace('/', '_')}.txt",
                            use_container_width=True,
                            type="primary"
                        )

                    except Exception as e:
                        st.error(f"❌ Erro na análise: {str(e)}")

                        # Tentar modelo alternativo
                        if 'tentativa_alternativa' not in st.session_state:
                            st.session_state.tentativa_alternativa = True
                            st.info("Tentando modelo alternativo...")

                            modelos_alternativos = [
                                "gemini-1.5-pro",
                                "gemini-1.5-flash",
                                "gemini-pro"
                            ]

                            for modelo_alt in modelos_alternativos:
                                try:
                                    st.session_state.modelo_selecionado = modelo_alt
                                    st.rerun()
                                except:
                                    continue

                        st.error("Nenhum modelo funcionou. Gere uma nova API Key em: https://aistudio.google.com/app/apikey")
            else:
                st.error("❌ Preencha todos os campos e anexe os PDFs!")

    except Exception as e:
        st.error(f"❌ Erro ao configurar API: {str(e)}")
        st.info("**Solução:** Gere uma nova API Key em: https://aistudio.google.com/app/apikey")

else:
    st.info("👆 Cole sua API Key do Google Gemini acima")
    st.markdown("### 🔑 Como obter API Key:")
    st.markdown("""
    1. Acesse: **https://aistudio.google.com/app/apikey**
    2. Faça login com Google
    3. Clique em **"Create API Key"**
    4. Escolha **"Create API key in new project"**
    5. Copie a chave (começa com AIza...)
    6. Cole no campo acima
    """)

st.divider()
st.markdown("🏛️ **Sistema de Validação com IA** • Prefeitura de Contagem")
