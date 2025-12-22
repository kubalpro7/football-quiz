import streamlit as st
import os
import random
import time
from PIL import Image

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Football Quiz PRO FINAL", layout="centered", page_icon="⚽")

# --- CSS (WYGLĄD) ---
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 700px;
    }
    .stApp { background-color: #0e1117; }
    
    /* Tablica wyników */
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 10px 15px; border-radius: 8px;
        font-size: 18px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 10px;
    }
    
    /* Zdjęcie */
    img {
        max-height: 350px !important;
        object-fit: contain;
        border-radius: 8px;
    }
    
    /* Karty graczy */
    .player-box {
        text-align: center; padding: 5px; border-radius: 5px; width: 100%; font-weight: bold; font-size: 14px;
    }
    .p1-box { background-color: #1b5e20; color: #a5d6a7; border: 1px solid #2e7d32; }
    .p2-box { background-color: #0d47a1; color: #90caf9; border: 1px solid #1565c0; }
    
    /* Alerty */
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 15px; margin: 5px 0; }
    
    /* Koniec gry / Walkower */
    .game-over-box {
        background-color: #b71c1c; color: white; padding: 20px; text-align: center;
        border-radius: 10px; font-size: 24px; font-weight: bold; margin-top: 20px;
    }
    .summary-box {
        background-color: #262730; padding: 20px; border-radius: 10px; margin-top: 10px; border: 1px solid #555;
    }
    
    /* Ukrycie elementów UI Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- GLOBALNY STAN SERWERA ---
class GlobalGameState:
    def __init__(self):
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby" # lobby, playing, round_over, finished, disconnected
        
        self.current_team = None
        self.current_image = None
        self.image_pool = []
        self.round_id = 0
        self.p1_locked = False
        self.p2_locked = False
        self.who_starts_next = "P1"
        self.winner_last_round = None
        self.last_correct_answer = ""
        
        # Mechanizm Heartbeat (Bicie serca)
        self.p1_last_seen = time.time()
        self.p2_last_seen = time.time()
        self.disconnect_reason = ""

@st.cache_resource
def get_server_state():
    return GlobalGameState()

server = get_server_state()

# --- LOKALNY STAN ---
if 'my_role' not in st.session_state:
    st.session_state.my_role = None

# --- FUNKCJE LOGIKI ---
def update_heartbeat(role):
    """Aktualizuje czas ostatniej aktywności gracza."""
    if role == "P1":
        server.p1_last_seen = time.time()
    elif role == "P2":
        server.p2_last_seen = time.time()

def check_disconnections():
    """Sprawdza czy ktoś nie zniknął (timeout 10 sekund)."""
    # Sprawdzamy tylko w trakcie gry
    if server.status not in ["playing", "round_over"]:
        return

    timeout = 8.0 # Sekundy tolerancji na brak sygnału
    now = time.time()
    
    # Jeśli P1 zniknął
    if now - server.p1_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p1_name} rozłączył się (zamknął grę)!"
    
    # Jeśli P2 zniknął
    elif now - server.p2_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p2_name} rozłączył się (zamknął grę)!"

def get_available_leagues(folder):
    if not os.path.exists(folder): return []
    leagues = []
    for item in os.listdir(folder):
        if os.path.isdir(os.path.join(folder, item)) and not item.startswith("."):
            leagues.append(item.replace("_", " "))
    return sorted(leagues)

def load_images_filtered(folder, selected_leagues):
    server.image_pool = []
    if not os.path.exists(folder): return
    for root, dirs, files in os.walk(folder):
        folder_parts = root.split(os.sep)
        match = False
        for part in folder_parts:
            if part.replace("_", " ") in selected_leagues:
                match = True
                break
        if match:
            for file in files:
                if file.lower().endswith(('.jpg', '.png', '.jpeg')):
                    team = os.path.basename(root).replace("_", " ")
                    if team == "." or team == folder: continue
                    full_path = os.path.join(root, file)
                    server.image_pool.append((team, full_path))

def start_new_round():
    if not server.image_pool: return
    team, img = random.choice(server.image_pool)
    server.current_team = team
    server.current_image = img
    server.p1_locked = False
    server.p2_locked = False
    server.status = "playing"
    server.winner_last_round = None
    server.round_id += 1

def handle_wrong_guess(role):
    if role == "P1":
        server.p1_locked = True
        server.p2_locked = False
    else:
        server.p2_locked = True
        server.p1_locked = False

def handle_win(winner):
    server.winner_last_round = winner
    server.last_correct_answer = server.current_team
    if winner == "P1":
        server.p1_score += 1
        server.who_starts_next = "P2"
    elif winner == "P2":
        server.p2_score += 1
        server.who_starts_next = "P1"
    server.status = "round_over"

def reset_game():
    server.p1_name = None
    server.p2_name = None
    server.p1_score = 0
    server.p2_score = 0
    server.status = "lobby"
    server.p1_locked = False
    server.p2_locked = False
    server.who_starts_next = "P1"
    server.p1_last_seen = time.time()
    server.p2_last_seen = time.time()

FOLDER_Z_KOSZULKAMI = "."

# --- SERCE SYSTEMU (Heartbeat) ---
# Wywołujemy to przy każdym odświeżeniu strony przez gracza
if st.session_state.my_role:
    update_heartbeat(st.session_state.my_role)

# Sprawdzamy czy ktoś nie uciekł
check_disconnections()

# ==============================================================================
# 1. LOBBY
# ==============================================================================
if server.status == "lobby":
    st.markdown("<h2 style='text-align: center;'>🏆 LOBBY</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name:
            st.success(f"✅ {server.p1_name}")
        else:
            n1 = st.text_input("Nick P1", key="n1")
            if st.button("Zajmij P1"):
                if n1:
                    server.p1_name = n1
                    st.session_state.my_role = "P1"
                    update_heartbeat("P1")
                    st.rerun()
    with col2:
        st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
        if server.p2_name:
            st.success(f"✅ {server.p2_name}")
        else:
            n2 = st.text_input("Nick P2", key="n2")
            if st.button("Zajmij P2"):
                if n2:
                    server.p2_name = n2
                    st.session_state.my_role = "P2"
                    update_heartbeat("P2")
                    st.rerun()

    st.divider()

    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia")
        all_leagues = get_available_leagues(FOLDER_Z_KOSZULKAMI)
        selected_leagues = st.multiselect("Wybierz ligi:", all_leagues, default=all_leagues)
        
        if server.p1_name and server.p2_name:
            if not selected_leagues:
                st.error("⚠️ Wybierz min. 1 ligę!")
            else:
                if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                    load_images_filtered(FOLDER_Z_KOSZULKAMI, selected_leagues)
                    if not server.image_pool:
                        st.error("Brak zdjęć!")
                    else:
                        # Reset czasu przy starcie, żeby nie wyrzuciło od razu
                        server.p1_last_seen = time.time()
                        server.p2_last_seen = time.time()
                        start_new_round()
                        st.rerun()
        else:
            st.warning("Czekamy na drugiego gracza...")
            time.sleep(1)
            st.rerun()
            
    elif st.session_state.my_role == "P2":
        st.info("Oczekiwanie na start gry...")
        time.sleep(1)
        st.rerun()
    else:
        time.sleep(1)
        st.rerun()

# ==============================================================================
# 2. ROZGRYWKA (PLAYING)
# ==============================================================================
elif server.status == "playing":
    # --- PRZYCISK ZAKOŃCZENIA GRY (Tylko dla P1) ---
    if st.session_state.my_role == "P1":
        if st.sidebar.button("🏁 ZAKOŃCZ GRĘ", type="primary"):
            server.status = "finished"
            st.rerun()

    st.markdown(f"""
    <div class="score-board">
        <span style="color: #66bb6a">{server.p1_name}: {server.p1_score}</span>
        <span style="font-size: 14px; color: #888">VS</span>
        <span style="color: #42a5f5">{server.p2_name}: {server.p2_score}</span>
    </div>
    """, unsafe_allow_html=True)

    if server.p1_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} PUDŁO! Tura: {server.p2_name}</div>", unsafe_allow_html=True)
    elif server.p2_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} PUDŁO! Tura: {server.p1_name}</div>", unsafe_allow_html=True)

    if server.current_image:
        try: st.image(Image.open(server.current_image), use_container_width=True)
        except: st.error("Błąd zdjęcia")

    all_teams = sorted(list(set([x[0] for x in server.image_pool])))
    guess = st.selectbox("Wybierz:", [""] + all_teams, key=f"g_{server.round_id}")

    c1, c2 = st.columns(2)
    
    if st.session_state.my_role == "P1":
        with c1:
            if server.p1_locked:
                st.button("⛔ Czekaj...", disabled=True, use_container_width=True)
            else:
                if st.button("ZGŁASZAM! 🎯", type="primary", use_container_width=True):
                    if guess == server.current_team:
                        handle_win("P1")
                        st.rerun()
                    else:
                        st.toast("ŹLE!", icon="❌")
                        handle_wrong_guess("P1")
                        st.rerun()
        with c2:
            if not server.p1_locked and st.button("🏳️ Poddaję"):
                handle_wrong_guess("P1")
                st.rerun()

    elif st.session_state.my_role == "P2":
        with c2:
            if server.p2_locked:
                st.button("⛔ Czekaj...", disabled=True, use_container_width=True)
            else:
                if st.button("ZGŁASZAM! 🎯", type="primary", use_container_width=True):
                    if guess == server.current_team:
                        handle_win("P2")
                        st.rerun()
                    else:
                        st.toast("ŹLE!", icon="❌")
                        handle_wrong_guess("P2")
                        st.rerun()
        with c1:
             if not server.p2_locked and st.button("🏳️ Poddaję"):
                handle_wrong_guess("P2")
                st.rerun()

    if server.p1_locked and server.p2_locked:
        st.warning("Obaj spudłowali!")
        if st.button("KONIEC RUNDY ➡️", use_container_width=True):
            server.winner_last_round = "NIKT"
            server.last_correct_answer = server.current_team
            server.status = "round_over"
            st.rerun()

    time.sleep(1) # Interval odświeżania (Heartbeat + Aktualizacja stanu)
    st.rerun()

# ==============================================================================
# 3. KONIEC RUNDY
# ==============================================================================
elif server.status == "round_over":
    # --- PRZYCISK ZAKOŃCZENIA GRY ---
    if st.session_state.my_role == "P1":
        if st.sidebar.button("🏁 ZAKOŃCZ GRĘ", type="primary"):
            server.status = "finished"
            st.rerun()

    if server.winner_last_round == "P1":
        bg, txt = "#1b5e20", f"🏆 Punkt dla: {server.p1_name}!"
    elif server.winner_last_round == "P2":
        bg, txt = "#0d47a1", f"🏆 Punkt dla: {server.p2_name}!"
    else:
        bg, txt = "#555", "💀 Remis / Nikt nie zgadł"
        
    st.markdown(f"<div class='winner-banner' style='background:{bg}; color:white'>{txt}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='correct-answer'>{server.last_correct_answer}</div>", unsafe_allow_html=True)
    
    if server.current_image: st.image(Image.open(server.current_image), use_container_width=True)

    st.divider()

    if server.winner_last_round == "NIKT": active_player = "P1"
    else: active_player = server.who_starts_next

    if st.session_state.my_role == active_player:
        st.success("Twoja kolej! Rozpocznij rundę.")
        if st.button("NASTĘPNA RUNDA ➡️", type="primary", use_container_width=True):
            start_new_round()
            st.rerun()
    else:
        st.info(f"Czekaj... {active_player} rozpoczyna rundę.")
        st.empty()
        time.sleep(1)
        st.rerun()

# ==============================================================================
# 4. EKRAN ROZŁĄCZENIA (Ktoś wyszedł)
# ==============================================================================
elif server.status == "disconnected":
    st.markdown(f"<div class='game-over-box'>🚨 WALKOWER! 🚨<br>{server.disconnect_reason}</div>", unsafe_allow_html=True)
    
    # Podsumowanie wyniku
    st.markdown(f"""
    <div class='summary-box'>
        <h3>Aktualny wynik:</h3>
        <p style='color:#66bb6a'>{server.p1_name}: {server.p1_score}</p>
        <p style='color:#42a5f5'>{server.p2_name}: {server.p2_score}</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("WRÓĆ DO LOBBY 🏠", type="primary"):
        reset_game()
        st.rerun()
        
    time.sleep(2)
    st.rerun()

# ==============================================================================
# 5. EKRAN ZAKOŃCZENIA (Manualne)
# ==============================================================================
elif server.status == "finished":
    st.markdown("<div class='game-over-box' style='background-color:#2e7d32'>🏁 KONIEC MECZU 🏁</div>", unsafe_allow_html=True)
    
    # Wyłonienie zwycięzcy
    if server.p1_score > server.p2_score:
        msg = f"🏆 WYGRYWA: {server.p1_name}!"
        color = "#66bb6a"
    elif server.p2_score > server.p1_score:
        msg = f"🏆 WYGRYWA: {server.p2_name}!"
        color = "#42a5f5"
    else:
        msg = "🤝 REMIS!"
        color = "#ffffff"

    st.markdown(f"<h1 style='text-align:center; color:{color}'>{msg}</h1>", unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class='summary-box' style='text-align:center'>
        <h2>WYNIK KOŃCOWY</h2>
        <h1>{server.p1_score} - {server.p2_score}</h1>
        <p>{server.p1_name} vs {server.p2_name}</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("ZAGRAJ OD NOWA (LOBBY) 🔄", type="primary", use_container_width=True):
        reset_game()
        st.rerun()

# RESET W PASKU BOCZNYM
if st.sidebar.button("HARD RESET SERWERA"):
    reset_game()
    st.rerun()


