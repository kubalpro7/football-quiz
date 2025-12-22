import streamlit as st
import os
import random
import time
from PIL import Image

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Football Quiz FINAL V6", layout="centered", page_icon="⚽")

# --- CSS (WYGLĄD) ---
st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        max-width: 750px;
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
    
    /* Banner zwycięzcy */
    .winner-banner {
        background-color: #ffd700; color: black; padding: 10px;
        text-align: center; border-radius: 8px; font-size: 20px; font-weight: bold; margin-bottom: 5px;
    }
    .correct-answer {
        font-size: 22px; color: #4CAF50; text-align: center; font-weight: bold; margin-bottom: 15px;
    }

    /* Ukrycie domyślnego menu Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Zmniejszenie odstępów w formularzu */
    .stForm { margin-top: 0px; }
    div[data-testid="stForm"] { border: none; padding: 0; }
    </style>
""", unsafe_allow_html=True)

# --- GLOBALNY STAN SERWERA ---
class GlobalGameState:
    def __init__(self):
        self.p1_name = None
        self.p2_name = None
        self.p1_score = 0
        self.p2_score = 0
        self.status = "lobby" 
        
        self.current_team = None
        self.current_image = None
        self.image_pool = []
        self.round_id = 0
        
        self.input_reset_counter = 0 
        self.current_round_starter = "P1" 
        
        self.p1_locked = False
        self.p2_locked = False
        self.who_starts_next = "P1"
        self.winner_last_round = None
        self.last_correct_answer = ""
        
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
    if role == "P1": server.p1_last_seen = time.time()
    elif role == "P2": server.p2_last_seen = time.time()

def check_disconnections():
    if server.status not in ["playing", "round_over"]: return
    timeout = 8.0
    now = time.time()
    if now - server.p1_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p1_name} rozłączył się!"
    elif now - server.p2_last_seen > timeout:
        server.status = "disconnected"
        server.disconnect_reason = f"Gracz {server.p2_name} rozłączył się!"

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
                match = True; break
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
    server.input_reset_counter = 0 
    server.current_round_starter = server.who_starts_next

def handle_wrong_guess(role):
    server.input_reset_counter += 1
    if role == "P1":
        server.p1_locked = True
        server.p2_locked = False
    else:
        server.p2_locked = True
        server.p1_locked = False

def handle_surrender(role):
    server.input_reset_counter += 1
    if role == "P1": server.p1_locked = True
    else: server.p2_locked = True

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

if st.session_state.my_role:
    update_heartbeat(st.session_state.my_role)
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

    # KONFIGURACJA (Tylko w Lobby!)
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
    # WYNIK
    st.markdown(f"""
    <div class="score-board">
        <span style="color: #66bb6a">{server.p1_name}: {server.p1_score}</span>
        <span style="font-size: 14px; color: #888">VS</span>
        <span style="color: #42a5f5">{server.p2_name}: {server.p2_score}</span>
    </div>
    """, unsafe_allow_html=True)

    # ALERTY
    if server.p1_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p1_name} PUDŁO! Tura: {server.p2_name}</div>", unsafe_allow_html=True)
    elif server.p2_locked:
        st.markdown(f"<div class='turn-alert'>❌ {server.p2_name} PUDŁO! Tura: {server.p1_name}</div>", unsafe_allow_html=True)

    # ZDJĘCIE
    if server.current_image:
        try: st.image(Image.open(server.current_image), use_container_width=True)
        except: st.error("Błąd zdjęcia")

    # UŻYCIE FORMULARZA ABY ENTER DZIAŁAŁ
    # Klucz formularza musi być unikalny per reset inputu
    with st.form(key=f"game_form_{server.round_id}_{server.input_reset_counter}"):
        
        # 1. Pole wyboru (wciśnięcie Enter w tym polu uruchomi pierwszy submit_button)
        all_teams = sorted(list(set([x[0] for x in server.image_pool])))
        guess = st.selectbox("Wybierz drużynę i wciśnij ENTER:", [""] + all_teams)

        # 2. Przyciski w jednej linii (Używamy kolumn wewnątrz formularza)
        if st.session_state.my_role == "P1":
            # Dla P1: Zgłaszam | Poddaję | Koniec Gry
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                submit_guess = st.form_submit_button("ZGŁASZAM 🎯", type="primary", use_container_width=True, disabled=server.p1_locked)
            with c2:
                submit_surrender = st.form_submit_button("Poddaję 🏳️", use_container_width=True, disabled=server.p1_locked)
            with c3:
                submit_end = st.form_submit_button("🏁 KONIEC", type="secondary", use_container_width=True)
        else:
            # Dla P2: Zgłaszam | Poddaję
            c1, c2 = st.columns([3, 1])
            with c1:
                submit_guess = st.form_submit_button("ZGŁASZAM 🎯", type="primary", use_container_width=True, disabled=server.p2_locked)
            with c2:
                submit_surrender = st.form_submit_button("Poddaję 🏳️", use_container_width=True, disabled=server.p2_locked)
            submit_end = False

    # OBSŁUGA AKCJI PO KLIKNIĘCIU (LUB ENTER)
    
    # Obsługa Końca Gry (Tylko P1)
    if st.session_state.my_role == "P1" and submit_end:
        server.status = "finished"
        st.rerun()

    # Obsługa Zgłoszenia
    if submit_guess:
        role = st.session_state.my_role
        # Sprawdzamy czy gracz nie jest zablokowany (zabezpieczenie backendowe)
        is_locked = server.p1_locked if role == "P1" else server.p2_locked
        
        if not is_locked:
            if guess == server.current_team:
                handle_win(role)
                st.rerun()
            else:
                st.toast("ŹLE! Blokada!", icon="❌")
                handle_wrong_guess(role)
                st.rerun()

    # Obsługa Poddania
    if submit_surrender:
        role = st.session_state.my_role
        handle_surrender(role)
        st.rerun()

    # OBAJ ZABLOKOWANI -> KONIEC RUNDY
    if server.p1_locked and server.p2_locked:
        server.winner_last_round = "NIKT"
        server.last_correct_answer = server.current_team
        if server.current_round_starter == "P1":
            server.who_starts_next = "P2"
        else:
            server.who_starts_next = "P1"
        server.status = "round_over"
        st.rerun()

    time.sleep(1)
    st.rerun()

# ==============================================================================
# 3. KONIEC RUNDY
# ==============================================================================
elif server.status == "round_over":
    # W sekcji Round Over przyciski też muszą być widoczne
    if st.session_state.my_role == "P1":
        if st.sidebar.button("🏁 ZAKOŃCZ GRĘ", type="primary"):
            server.status = "finished"
            st.rerun()

    if server.winner_last_round == "P1":
        bg, txt = "#1b5e20", f"🏆 Punkt dla: {server.p1_name}!"
    elif server.winner_last_round == "P2":
        bg, txt = "#0d47a1", f"🏆 Punkt dla: {server.p2_name}!"
    else:
        bg, txt = "#555", "💀 Nikt nie zgadł (Poddanie)"
        
    st.markdown(f"<div class='winner-banner' style='background:{bg}; color:white'>{txt}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='correct-answer'>{server.last_correct_answer}</div>", unsafe_allow_html=True)
    
    if server.current_image: st.image(Image.open(server.current_image), use_container_width=True)

    st.divider()

    active_player = server.who_starts_next
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
# 4. ROZŁĄCZENIE / WALKOWER
# ==============================================================================
elif server.status == "disconnected":
    st.markdown(f"<div class='game-over-box'>🚨 WALKOWER! 🚨<br>{server.disconnect_reason}</div>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='background-color:#262730; padding:20px; border-radius:10px; margin-top:10px; text-align:center;'>
        <h3>Aktualny wynik:</h3>
        <p style='color:#66bb6a; font-size:20px'>{server.p1_name}: {server.p1_score}</p>
        <p style='color:#42a5f5; font-size:20px'>{server.p2_name}: {server.p2_score}</p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("WRÓĆ DO LOBBY 🏠", type="primary"):
        reset_game()
        st.rerun()
    time.sleep(2)
    st.rerun()

# ==============================================================================
# 5. KONIEC MECZU (MANUALNY)
# ==============================================================================
elif server.status == "finished":
    st.markdown("<div class='game-over-box' style='background-color:#2e7d32'>🏁 KONIEC MECZU 🏁</div>", unsafe_allow_html=True)
    if server.p1_score > server.p2_score:
        msg, color = f"🏆 WYGRYWA: {server.p1_name}!", "#66bb6a"
    elif server.p2_score > server.p1_score:
        msg, color = f"🏆 WYGRYWA: {server.p2_name}!", "#42a5f5"
    else:
        msg, color = "🤝 REMIS!", "#ffffff"

    st.markdown(f"<h1 style='text-align:center; color:{color}'>{msg}</h1>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='background-color:#262730; padding:20px; border-radius:10px; margin-top:10px; text-align:center;'>
        <h1>{server.p1_score} - {server.p2_score}</h1>
    </div>
    """, unsafe_allow_html=True)

    if st.button("ZAGRAJ OD NOWA (LOBBY) 🔄", type="primary", use_container_width=True):
        reset_game()
        st.rerun()

if st.sidebar.button("HARD RESET SERWERA"):
    reset_game()
    st.rerun()



