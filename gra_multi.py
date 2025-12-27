import streamlit as st
import os
import random
import time
import pandas as pd
import requests
from io import BytesIO
from PIL import Image

# ==============================================================================
# 1. KONFIGURACJA UI I CSS
# ==============================================================================
st.set_page_config(page_title="Football Quiz Ultimate", layout="centered", page_icon="⚽")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 5rem !important; max-width: 800px; }
    .stApp { background-color: #0e1117; }
    #MainMenu, footer, header {visibility: hidden;}
    
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 22px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    img { max-height: 400px !important; object-fit: contain; border-radius: 12px; margin-bottom: 10px; }
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 18px; margin: 10px 0; }
    
    div[data-testid="column"] { display: flex; align-items: center; justify-content: center; }
    button { height: 50px !important; font-size: 16px !important; }
    
    .room-card { 
        border: 1px solid #444; padding: 15px; border-radius: 10px; 
        background: #1e2128; text-align: center; margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- GLOBALNE FILTRY ---
TOP_20_CLUBS = [
    "Manchester City", "Real Madrid", "Bayern Munich", "Liverpool", "Inter Milan",
    "Bayer Leverkusen", "Arsenal", "Barcelona", "Atletico Madrid", "PSG",
    "Borussia Dortmund", "Juventus", "RB Leipzig", "Atalanta", "Benfica",
    "Chelsea", "AC Milan", "Sporting CP", "Napoli", "Tottenham",
    "Paris Saint Germain", "Inter", "Milan", "Bayer 04 Leverkusen"
]

GAME_MODES = {
    "👕 Koszulki (Ligi)": ("baza_zdjec.csv", "Jaki to klub?"),
    "👤 Sylwetki Piłkarzy": ("sylwetki_pilkarzy.csv", "Kto to jest?"),
    "🛡️ Herby Klubowe": ("herby_klubowe.csv", "Do kogo należy ten herb?")
}

# ==============================================================================
# 2. CACHOWANIE DANYCH (Optymalizacja wydajności)
# ==============================================================================
@st.cache_data
def load_csv_data(file_path):
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return None

# ==============================================================================
# 3. ZARZĄDZANIE POKOJAMI (Multi-Room)
# ==============================================================================

class GameState:
    """Stan pojedynczego pokoju gry"""
    def __init__(self, room_id):
        self.room_id = room_id
        self.created_at = time.time()
        self.last_activity = time.time()
        
        self.mode = "multi" # multi / solo
        self.p1_name = None; self.p2_name = None
        self.p1_score = 0; self.p2_score = 0
        self.status = "lobby" # lobby / playing / round_over / finished / disconnected
        
        self.current_team = None; self.current_image = None
        self.image_pool = []; self.round_id = 0; self.input_reset_counter = 0
        self.current_round_starter = "P1"; self.who_starts_next = "P1"
        self.p1_locked = False; self.p2_locked = False
        self.winner_last_round = None; self.last_correct_answer = ""
        
        self.p1_last_seen = time.time(); self.p2_last_seen = time.time()
        self.disconnect_reason = ""
        self.active_category_name = list(GAME_MODES.keys())[0]

class RoomManager:
    """Zarządza wszystkimi pokojami na serwerze"""
    def __init__(self):
        self.rooms = {} 

    def get_room(self, room_id):
        self.cleanup_rooms()
        if room_id not in self.rooms:
            self.rooms[room_id] = GameState(room_id)
        self.rooms[room_id].last_activity = time.time()
        return self.rooms[room_id]

    def cleanup_rooms(self):
        """Usuwa pokoje, w których nikt nie grał od 10 minut"""
        now = time.time()
        timeout = 600.0 
        to_delete = [rid for rid, r in self.rooms.items() if now - r.last_activity > timeout]
        for rid in to_delete: del self.rooms[rid]

@st.cache_resource
def get_manager(): return RoomManager()
manager = get_manager()

# ==============================================================================
# 4. LOGIKA POMOCNICZA
# ==============================================================================

def load_images_filtered(server, csv_path, selected_leagues, use_top_20_filter=False):
    server.image_pool = []
    df = load_csv_data(csv_path)
    if df is None: return

    try:
        temp_df = df.copy()
        if selected_leagues: 
            temp_df = temp_df[temp_df['Liga'].isin(selected_leagues)]
        
        if use_top_20_filter:
            col = next((c for c in ['Klub_Filter', 'Klub', 'Odpowiedz'] if c in temp_df.columns), None)
            if col: temp_df = temp_df[temp_df[col].isin(TOP_20_CLUBS)]
        
        ans_col = 'Odpowiedz' if 'Odpowiedz' in temp_df.columns else 'Klub'
        for _, row in temp_df.iterrows():
            server.image_pool.append((row[ans_col], row['Link_Bezposredni']))
    except Exception as e: st.error(f"Błąd danych: {e}")

def start_new_round(server):
    if not server.image_pool: return
    team, img_url = random.choice(server.image_pool)
    server.current_team = team; server.current_image = img_url
    server.p1_locked = False; server.p2_locked = False
    server.status = "playing"; server.winner_last_round = None
    server.round_id += 1; server.input_reset_counter = 0
    if server.mode == "solo": server.current_round_starter = "P1"
    else: server.current_round_starter = server.who_starts_next

def handle_guess(server, guess): return guess == server.current_team

def handle_win(server, winner):
    server.winner_last_round = winner; server.last_correct_answer = server.current_team
    if winner == "P1": server.p1_score += 1; server.who_starts_next = "P2"
    else: server.p2_score += 1; server.who_starts_next = "P1"
    server.status = "round_over"

def update_heartbeat(server, role):
    if role == "P1": server.p1_last_seen = time.time()
    elif role == "P2": server.p2_last_seen = time.time()
    server.last_activity = time.time()

def check_disconnections(server):
    if server.mode == "solo" or server.status not in ["playing", "round_over"]: return
    now = time.time()
    limit = 15.0
    if now - server.p1_last_seen > limit:
        server.status="disconnected"; server.disconnect_reason=f"{server.p1_name} rozłączył się!"
    elif now - server.p2_last_seen > limit:
        server.status="disconnected"; server.disconnect_reason=f"{server.p2_name} rozłączył się!"

def reset_game(server):
    server.mode="multi"; server.p1_name=None; server.p2_name=None; server.p1_score=0; server.p2_score=0
    server.status="lobby"; server.p1_locked=False; server.p2_locked=False; server.who_starts_next="P1"

# ==============================================================================
# 5. WIDOKI (UI)
# ==============================================================================

def view_main_menu():
    st.markdown("<h1 style='text-align: center;'>⚽ FOOTBALL QUIZ</h1>", unsafe_allow_html=True)
    
    with st.container(border=True):
        st.write("### 🚪 Wejdź do gry")
        room_input = st.text_input("Podaj nazwę pokoju (np. Stolik1):", key="room_in").strip()
        if st.button("DOŁĄCZ / STWÓRZ 🚪", type="primary", use_container_width=True):
            if room_input:
                st.session_state.current_room_id = room_input
                st.rerun()
            else: st.warning("Wpisz nazwę pokoju!")

    # Lista aktywnych pokoi
    manager.cleanup_rooms()
    active = list(manager.rooms.keys())
    if active:
        st.write("---")
        st.write("### 🟢 Aktywne stoliki:")
        cols = st.columns(3)
        for i, rid in enumerate(active):
            with cols[i % 3]:
                if st.button(f"Stolik: {rid}", key=f"join_{rid}", use_container_width=True):
                    st.session_state.current_room_id = rid
                    st.rerun()

def view_game_lobby(server):
    st.markdown(f"<h3 style='text-align: center;'>Stolik: {server.room_id}</h3>", unsafe_allow_html=True)
    if st.sidebar.button("🔙 Menu Główne"):
        del st.session_state.current_room_id; st.session_state.my_role = None; st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='player-box' style='background:#1b5e20; padding:10px; border-radius:5px; text-align:center;'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name: st.success(f"✅ {server.p1_name}")
        else:
            n = st.text_input("Twój Nick (P1)", key="n1")
            cc1, cc2 = st.columns(2)
            if cc1.button("Hostuj", use_container_width=True): 
                if n: server.p1_name=n; server.mode="multi"; st.session_state.my_role="P1"; st.rerun()
            if cc2.button("Solo", use_container_width=True): 
                if n: server.p1_name=n; server.mode="solo"; server.p2_name="CPU"; st.session_state.my_role="P1"; st.rerun()
    with c2:
        if server.mode=="solo": st.info("Tryb Jednoosobowy")
        else:
            st.markdown("<div class='player-box' style='background:#0d47a1; padding:10px; border-radius:5px; text-align:center;'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
            if server.p2_name: st.success(f"✅ {server.p2_name}")
            else:
                n = st.text_input("Twój Nick (P2)", key="n2")
                if st.button("Dołącz jako P2", use_container_width=True): 
                    if n: server.p2_name=n; server.mode="multi"; st.session_state.my_role="P2"; st.rerun()

    st.divider()
    
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Konfiguracja")
        cat = st.selectbox("Wybierz kategorię:", list(GAME_MODES.keys()))
        csv_file, _ = GAME_MODES[cat]
        
        all_leagues = sorted(list(set(load_csv_data(csv_file)['Liga'].dropna()))) if load_csv_data(csv_file) is not None else []
        sel_leagues = st.multiselect("Ligi:", all_leagues, default=all_leagues)
        use_top20 = st.checkbox("🏆 Tylko Top 20 (Ranking)", value=False)
        
        ready = (server.mode=="solo" and server.p1_name) or (server.mode=="multi" and server.p1_name and server.p2_name)
        if ready:
            if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                if not sel_leagues: st.error("Wybierz min. jedną ligę!")
                else:
                    load_images_filtered(server, csv_file, sel_leagues, use_top20)
                    server.active_category_name = cat
                    start_new_round(server); st.rerun()
        elif server.mode == "multi": st.warning("⏳ Czekamy na przeciwnika...")
    
    elif st.session_state.my_role == "P2": st.info("⏳ Czekaj, aż Gospodarz wystartuje grę...")

    time.sleep(1.5); st.rerun()

def view_playing(server):
    _, q_label = GAME_MODES.get(server.active_category_name, ("", "Wybierz:"))
    st.caption(f"Stolik: {server.room_id} | {server.active_category_name}")
    
    # Tablica wyników
    if server.mode=="solo":
        st.markdown(f"<div class='score-board' style='justify-content:center; color:#66bb6a'>WYNIK: {server.p1_score}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='score-board'><span style='color:#66bb6a'>{server.p1_name}: {server.p1_score}</span><span style='color:#888'>VS</span><span style='color:#42a5f5'>{server.p2_name}: {server.p2_score}</span></div>", unsafe_allow_html=True)
    
    if server.mode=="multi":
        if server.p1_locked: st.warning(f"❌ {server.p1_name} PUDŁO! Tura: {server.p2_name}")
        elif server.p2_locked: st.warning(f"❌ {server.p2_name} PUDŁO! Tura: {server.p1_name}")

    # Pobieranie obrazu (Pancerna metoda requests)
    if server.current_image:
        try:
            r = requests.get(server.current_image, timeout=10); r.raise_for_status()
            st.image(Image.open(BytesIO(r.content)), use_container_width=True)
        except: st.error("⚠️ Problem z pobraniem obrazu.")

    opts = sorted(list(set([x[0] for x in server.image_pool]))) if server.image_pool else []
    
    with st.form(f"game_form_{server.round_id}_{server.input_reset_counter}"):
        guess = st.selectbox(q_label, [""] + opts)
        c1, c2 = st.columns([3, 1])
        submitted = c1.form_submit_button("SPRAWDŹ 🎯", type="primary", use_container_width=True)
        surrendered = c2.form_submit_button("🏳️", use_container_width=True)
        if st.session_state.my_role == "P1": st.form_submit_button("Koniec Meczu", on_click=lambda: setattr(server, 'status', 'finished'))

    role = st.session_state.my_role
    if submitted and guess:
        locked = (role=="P1" and server.p1_locked) or (role=="P2" and server.p2_locked) if server.mode=="multi" else False
        if not locked:
            if handle_guess(server, guess): handle_win(server, role); st.rerun()
            else:
                server.input_reset_counter += 1
                if server.mode=="multi":
                    if role=="P1": server.p1_locked=True; server.p2_locked=False
                    else: server.p2_locked=True; server.p1_locked=False
                st.toast("ŹLE!"); st.rerun()

    if surrendered:
        server.input_reset_counter += 1
        if server.mode=="solo": server.winner_last_round="NIKT"; server.last_correct_answer=server.current_team; server.status="round_over"
        elif role=="P1": server.p1_locked=True
        else: server.p2_locked=True
        st.rerun()

    if server.mode=="multi":
        if server.p1_locked and server.p2_locked:
            server.winner_last_round="NIKT"; server.last_correct_answer=server.current_team
            server.who_starts_next = "P2" if server.current_round_starter=="P1" else "P1"
            server.status="round_over"; st.rerun()
        time.sleep(1); st.rerun()

def view_round_over(server):
    col, txt = ("#555", "NIKT")
    if server.winner_last_round=="P1": col, txt = ("#1b5e20", server.p1_name)
    elif server.winner_last_round=="P2": col, txt = ("#0d47a1", server.p2_name)
    
    st.markdown(f"<div style='background:{col}; color:white; padding:15px; border-radius:10px; text-align:center;'><h3>Punkt dla: {txt}</h3></div>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center; color:#4CAF50;'>{server.last_correct_answer}</h3>", unsafe_allow_html=True)
    
    if server.current_image:
        try: st.image(Image.open(BytesIO(requests.get(server.current_image).content)), use_container_width=True)
        except: pass

    st.divider()
    nxt = server.who_starts_next if server.mode=="multi" else "P1"
    if st.session_state.my_role == nxt:
        if st.button("NASTĘPNA RUNDA ➡️", type="primary", use_container_width=True): start_new_round(server); st.rerun()
    else: st.info(f"Czekaj, aż {nxt} rozpocznie nową rundę..."); time.sleep(1.5); st.rerun()

def view_finished(server):
    st.title("🏁 KONIEC MECZU")
    st.header(f"WYNIK: {server.p1_score} - {server.p2_score}")
    if st.button("LOBBY STOLIKA 🔄", use_container_width=True): reset_game(server); st.rerun()
    if st.button("ZMIEŃ STOLIK 🚪", use_container_width=True): del st.session_state.current_room_id; st.rerun()

def view_disconnected(server):
    st.error(f"🚨 {server.disconnect_reason}")
    if st.button("POWRÓT DO LOBBY 🏠"): reset_game(server); st.rerun()
    time.sleep(2); st.rerun()

# ==============================================================================
# 6. FUNKCJA GŁÓWNA
# ==============================================================================

def main():
    if 'current_room_id' not in st.session_state:
        view_main_menu()
    else:
        room_id = st.session_state.current_room_id
        server = manager.get_room(room_id)
        
        if 'my_role' not in st.session_state: st.session_state.my_role = None
        if st.session_state.my_role: update_heartbeat(server, st.session_state.my_role)
        
        check_disconnections(server)

        if server.status == "lobby": view_game_lobby(server)
        elif server.status == "playing": view_playing(server)
        elif server.status == "round_over": view_round_over(server)
        elif server.status == "finished": view_finished(server)
        elif server.status == "disconnected": view_disconnected(server)

if __name__ == "__main__":
    main()
















