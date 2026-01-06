import streamlit as st
import google.generativeai as genai
import PyPDF2
from datetime import datetime

st.set_page_config(page_title="Validação de Projetos", page_icon="🏛️", layout="wide")

st.title("🏛️ Sistema de Validação de Projetos")
st.markdown("**Prefeitura de Contagem** — Análise Inteligente com Google Gemini")

# Configuração API
st.header("⚙️ Configuração")
api_key = st.text_input("Cole sua API Key do Google Gemini:", type="password")

if api_key:
    st.success("✅ API configurada!")

    try:
        genai.configure(api_key=api_key)

        # Verificar modelos disponíveis
        with st.expander("🔍 Ver modelos disponíveis na sua API"):
            try:
                modelos_disponiveis = []
                for m in genai.list_models():
                    if 'generateContent' in m.supported_generation_methods:
                        st.write(f"✅ {m.name}")
                        modelos_disponiveis.append(m.name)

                if not modelos_disponiveis:
                    st.warning("Nenhum modelo disponível. Verifique sua API Key.")
            except Exception as e:
                st.error(f"Erro ao listar modelos: {str(e)}")

        st.divider()
        st.header("📄 Upload de Documentos")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📐 PDFs do Projeto")
            projetos = st.file_uploader("Anexe os PDFs do projeto", type=['pdf'], accept_multiple_files=True, key="proj")
            if projetos:
                st.success(f"✅ {len(projetos)} arquivo(s)")

        with col2:
            st.subheader("📜 PDFs da Legislação")
            legislacoes = st.file_uploader("Anexe os PDFs da legislação", type=['pdf'], accept_multiple_files=True, key="leg")
            if legislacoes:
                st.success(f"✅ {len(legislacoes)} arquivo(s)")

        st.divider()
        st.header("📋 Dados do Processo")

        col1, col2, col3 = st.columns(3)

        with col1:
            numero = st.text_input("Número do Processo", placeholder="Ex: 2024.001")
        with col2:
            requerente = st.text_input("Requerente")
        with col3:
            area = st.number_input("Área (m²)", min_value=0.0, step=0.1)

        st.divider()
        st.subheader("📏 Regras a Verificar")
        regras = st.text_area(
            "Digite as regras (uma por linha):", 
            height=150,
            placeholder="Ex:\nArt. 10 - Área mínima 50m²\nArt. 15 - Recuo frontal 5m"
        )

        st.divider()

        if st.button("🔍 ANALISAR COM IA", type="primary", use_container_width=True):
            if projetos and legislacoes and numero and requerente and regras:
                with st.spinner("🤖 Analisando..."):
                    try:
                        # Extrair textos
                        texto_proj = ""
                        for idx, pdf in enumerate(projetos, 1):
                            reader = PyPDF2.PdfReader(pdf)
                            for num_pag, page in enumerate(reader.pages, 1):
                                texto_proj += f"\n[PROJETO {idx} - Pág {num_pag}]\n{page.extract_text()}\n"

                        texto_leg = ""
                        for idx, pdf in enumerate(legislacoes, 1):
                            reader = PyPDF2.PdfReader(pdf)
                            for num_pag, page in enumerate(reader.pages, 1):
                                texto_leg += f"\n[LEI {idx} - Pág {num_pag}]\n{page.extract_text()}\n"

                        # TENTAR DIFERENTES MODELOS
                        modelos_tentar = [
                            'models/gemini-pro',
                            'models/gemini-1.5-pro-latest',
                            'models/gemini-1.5-flash-latest',
                            'gemini-pro'
                        ]

                        model = None
                        erro_modelo = None

                        for nome_modelo in modelos_tentar:
                            try:
                                model = genai.GenerativeModel(nome_modelo)
                                st.info(f"✅ Usando modelo: {nome_modelo}")
                                break
                            except Exception as e:
                                erro_modelo = str(e)
                                continue

                        if not model:
                            st.error(f"❌ Nenhum modelo disponível. Erro: {erro_modelo}")
                            st.info("Tente gerar uma nova API Key em: https://aistudio.google.com/app/apikey")
                            st.stop()

                        # Prompt
                        prompt = f"""Analista técnico da Prefeitura de Contagem - MG.

PROCESSO: {numero}
REQUERENTE: {requerente}
ÁREA: {area}m²

LEGISLAÇÃO:
{texto_leg[:4000]}

REGRAS:
{regras}

PROJETO:
{texto_proj[:6000]}

Analise detalhadamente:

## ✅ CONFORMIDADES
(cite artigos específicos)

## ❌ NÃO CONFORMIDADES
(cite artigos, problemas e localização)

## ⚠️ PONTOS DE ATENÇÃO

## 🔧 RECOMENDAÇÕES

## 📊 PARECER
APROVADO ou REPROVADO (justifique citando artigos)
"""

                        response = model.generate_content(prompt)

                        st.divider()
                        st.header("📋 RELATÓRIO")

                        texto_resp = response.text.upper()
                        if "APROVADO" in texto_resp and "REPROVADO" not in texto_resp:
                            st.success("✅ APROVADO")
                        elif "REPROVADO" in texto_resp:
                            st.error("❌ REPROVADO")

                        st.markdown(response.text)

                        # Download
                        relatorio = f"""PREFEITURA DE CONTAGEM
RELATÓRIO DE ANÁLISE

Processo: {numero}
Requerente: {requerente}
Área: {area}m²
Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}

{response.text}
"""

                        st.download_button(
                            "📥 BAIXAR RELATÓRIO",
                            relatorio,
                            f"relatorio_{numero.replace('.', '_')}.txt",
                            use_container_width=True,
                            type="primary"
                        )

                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
            else:
                st.error("❌ Preencha todos os campos!")

    except Exception as e:
        st.error(f"❌ Erro na API: {str(e)}")

else:
    st.info("👆 Cole sua API Key acima")
    st.markdown("[🔗 Obter API Key](https://aistudio.google.com/app/apikey)")

st.divider()
st.markdown("🏛️ **Sistema de Validação** • Prefeitura de Contagem")
