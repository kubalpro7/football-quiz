import streamlit as st
import os
import random
import time
from PIL import Image

# --- KONFIGURACJA ---
FOLDER_Z_KOSZULKAMI = "."  # Na chmurze pliki będą w głównym katalogu

st.set_page_config(page_title="Global Football Quiz", layout="centered", page_icon="🌍")

# --- STYL CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .score-board {
        display: flex; justify-content: space-between; 
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444;
    }
    .vs-badge {
        background: #ff4b4b; color: white; padding: 5px 15px; 
        border-radius: 20px; font-style: italic;
    }
    </style>
""", unsafe_allow_html=True)

# --- GLOBALNY STAN GRY (SERVER-SIDE) ---
# To jest serce gry online. Zamiast pliku, używamy klasy w pamięci RAM.
class GlobalGameState:
    def __init__(self):
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby"
        self.current_team = None
        self.current_image = None
        self.winner_last_round = None
        self.image_pool = []
        self.last_action_time = time.time()

# @st.cache_resource sprawia, że ten obiekt jest JEDEN dla WSZYSTKICH użytkowników
@st.cache_resource
def get_server_state():
    return GlobalGameState()

# Pobieramy stan z pamięci serwera
server = get_server_state()

# --- FUNKCJE ---
def load_images_once():
    """Ładuje zdjęcia tylko raz przy starcie."""
    if server.image_pool: return # Jeśli już załadowane, nie rób nic
    
    if not os.path.exists(FOLDER_Z_KOSZULKAMI): return
    
    images = []
    # Skanowanie folderów (dostosowane do struktury GitHub)
    for root, dirs, files in os.walk(FOLDER_Z_KOSZULKAMI):
        for file in files:
            if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                # Zakładamy strukturę: Liga/Druzyna/zdjecie.jpg
                # Wyciągamy nazwę folderu w którym jest plik
                team = os.path.basename(root).replace("_", " ")
                # Jeśli plik jest luzem, pomiń lub nazwij "Unknown"
                if team == "." or team == FOLDER_Z_KOSZULKAMI: continue
                
                full_path = os.path.join(root, file)
                images.append((team, full_path))
    
    server.image_pool = images
    # Losujemy pierwsze zdjęcie na start
    if server.image_pool:
        new_round_logic()

def new_round_logic():
    if not server.image_pool: return
    team, img = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img
    server.winner_last_round = None
    server.last_action_time = time.time()

def reset_game():
    server.p1_name = None
    server.p2_name = None
    server.p1_score = 0
    server.p2_score = 0
    server.status = "lobby"
    new_round_logic()

# --- ŁADOWANIE ZDJĘĆ NA STARCIE ---
load_images_once()

# --- AUTO-ODŚWIEŻANIE ---
# To sprawia, że gra działa w czasie rzeczywistym
if server.status == "playing" or (server.p1_name and not server.p2_name):
    time.sleep(1)
    st.empty() # Wymusza re-render

# --- INTERFEJS ---
st.title("🌍 1vs1 WORLD CUP")

# 1. EKRAN LOBBY
if server.status == "lobby":
    st.info("Czekamy na graczy...")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Gospodarz (P1)")
        if server.p1_name:
            st.success(f"Gotowy: {server.p1_name}")
        else:
            nick1 = st.text_input("Nick P1")
            if st.button("Dołącz jako P1"):
                if nick1:
                    server.p1_name = nick1
                    st.rerun()

    with c2:
        st.subheader("Gość (P2)")
        if server.p2_name:
            st.success(f"Gotowy: {server.p2_name}")
        else:
            nick2 = st.text_input("Nick P2")
            if st.button("Dołącz jako P2"):
                if nick2:
                    server.p2_name = nick2
                    st.rerun()

    st.divider()
    if server.p1_name and server.p2_name:
        if st.button("START MECZU ⚽", type="primary", use_container_width=True):
            server.status = "playing"
            st.rerun()
            
    if st.sidebar.button("Resetuj Serwer"):
        reset_game()
        st.rerun()

# 2. EKRAN GRY
elif server.status == "playing":
    
    # Wynik
    st.markdown(f"""
    <div class="score-board">
        <span style="color: #4CAF50">{server.p1_name}: {server.p1_score}</span>
        <span class="vs-badge">VS</span>
        <span style="color: #2196F3">{server.p2_name}: {server.p2_score}</span>
    </div>
    """, unsafe_allow_html=True)

    # Zwycięzca rundy
    if server.winner_last_round:
        st.success(f"Rundę wygrywa: {server.winner_last_round}! (+1 pkt)")
        if st.button("Następna Runda ➡️"):
            new_round_logic()
            st.rerun()
        st.stop() # Zatrzymaj, żeby gracze zobaczyli wynik

    # Zdjęcie
    if server.current_image:
        try:
            img = Image.open(server.current_image)
            st.image(img, use_container_width=True)
        except:
            st.error("Błąd ładowania zdjęcia")
            new_round_logic()
            st.rerun()

    # Formularz
    all_teams_list = sorted(list(set([x[0] for x in server.image_pool])))
    
    # Używamy unikalnego klucza (czas), żeby resetować selectbox co rundę
    user_guess = st.selectbox("Jaka to drużyna?", [""] + all_teams_list, key=f"guess_{server.last_action_time}")

    c1, c2 = st.columns(2)
    
    with c1:
        if st.button(f"Zgłasza {server.p1_name}", type="secondary", use_container_width=True):
            if user_guess == server.current_team:
                server.p1_score += 1
                server.winner_last_round = server.p1_name
                st.rerun()
            else:
                st.toast(f"Źle! To nie {user_guess}", icon="❌")

    with c2:
        if st.button(f"Zgłasza {server.p2_name}", type="secondary", use_container_width=True):
            if user_guess == server.current_team:
                server.p2_score += 1
                server.winner_last_round = server.p2_name
                st.rerun()
            else:
                st.toast(f"Źle! To nie {user_guess}", icon="❌")

    if st.button("Pomiń tę rundę (Nikt nie wie)"):
        new_round_logic()
        st.rerun()