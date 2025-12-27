import streamlit as st
import os
import random
import time
import pandas as pd
import requests
from io import BytesIO
from PIL import Image

# ==============================================================================
# 1. KONFIGURACJA I STYL
# ==============================================================================
st.set_page_config(page_title="Football Quiz Live", layout="centered", page_icon="⚽")

st.markdown("""
    <style>
    .block-container { padding-top: 2rem !important; padding-bottom: 5rem !important; max-width: 800px; }
    .stApp { background-color: #0e1117; }
    #MainMenu, footer, header {visibility: hidden;}
    .score-board {
        display: flex; justify-content: space-between; align-items: center;
        background: #262730; padding: 15px; border-radius: 10px;
        font-size: 20px; font-weight: bold; color: white;
        border: 1px solid #444; margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    img { max-height: 400px !important; object-fit: contain; border-radius: 12px; margin-bottom: 10px; }
    .turn-alert { text-align: center; color: #ffca28; font-weight: bold; font-size: 18px; margin: 10px 0; }
    div[data-testid="column"] { display: flex; align-items: center; justify-content: center; }
    button { height: 50px !important; font-size: 16px !important; }
    .room-box { border: 2px dashed #444; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# Lista Top 20 (Filtry)
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
# 2. ZARZĄDZANIE POKOJAMI
# ==============================================================================

class GameState:
    """Stan pojedynczego stolika gry"""
    def __init__(self, room_id):
        self.room_id = room_id
        self.created_at = time.time()  # Data stworzenia
        
        # Ostatnia aktywność (ping) graczy - inicjujemy czasem obecnym
        self.p1_last_seen = time.time()
        self.p2_last_seen = time.time()
        
        self.mode = "multi"
        self.p1_name = None; self.p2_name = None
        self.p1_score = 0; self.p2_score = 0
        self.status = "lobby"
        self.current_team = None; self.current_image = None
        self.image_pool = []; self.round_id = 0; self.input_reset_counter = 0
        self.current_round_starter = "P1"; self.who_starts_next = "P1"
        self.p1_locked = False; self.p2_locked = False
        self.winner_last_round = None; self.last_correct_answer = ""
        self.disconnect_reason = ""
        self.active_category_name = "👕 Koszulki (Ligi)"

class RoomManager:
    """Zarządza wieloma stolikami"""
    def __init__(self):
        self.rooms = {} 

    def get_room(self, room_id):
        # Najpierw sprzątaj puste pokoje
        self.cleanup_rooms()
        
        if room_id not in self.rooms:
            self.rooms[room_id] = GameState(room_id)
        return self.rooms[room_id]

    def cleanup_rooms(self):
        now = time.time()
        timeout = 10.0  # Czas (sekundy) bez sygnału, po którym usuwamy pokój
        
        to_delete = []
        for rid, room in self.rooms.items():
            # Sprawdzamy, czy gracze są online (czy wysłali sygnał w ciągu ostatnich X sekund)
            # Jeśli gracz nie ma imienia (nie dołączył), to nie jest online.
            p1_online = (now - room.p1_last_seen < timeout) 
            p2_online = (now - room.p2_last_seen < timeout)
            
            # Zabezpieczenie: Nie usuwaj pokoju, który powstał przed chwilą (daj mu 15s na rozruch)
            is_just_created = (now - room.created_at < 15.0)

            # Jeśli nikt nie jest online i pokój nie jest nowy -> USUŃ
            if not p1_online and not p2_online and not is_just_created:
                to_delete.append(rid)
        
        for rid in to_delete:
            del self.rooms[rid]

@st.cache_resource
def get_manager(): return RoomManager()
manager = get_manager()

# ==============================================================================
# 3. LOGIKA GRY
# ==============================================================================

def get_available_leagues(csv_path):
    if not os.path.exists(csv_path): return []
    try:
        df = pd.read_csv(csv_path)
        if 'Liga' in df.columns: return sorted(df['Liga'].dropna().unique().tolist())
        return []
    except: return []

def load_images_filtered(server, csv_path, selected_leagues, use_top_20_filter=False):
    server.image_pool = []
    if not os.path.exists(csv_path): return

    try:
        df = pd.read_csv(csv_path)
        if selected_leagues: df = df[df['Liga'].isin(selected_leagues)]
        
        if use_top_20_filter:
            col_to_check = None
            if 'Klub_Filter' in df.columns: col_to_check = 'Klub_Filter'
            elif 'Klub' in df.columns: col_to_check = 'Klub'
            elif 'Odpowiedz' in df.columns: col_to_check = 'Odpowiedz'
            if col_to_check: df = df[df[col_to_check].isin(TOP_20_CLUBS)]
        
        ans_col = 'Odpowiedz' if 'Odpowiedz' in df.columns else 'Klub'
        for _, row in df.iterrows():
            server.image_pool.append((row[ans_col], row['Link_Bezposredni']))
    except Exception as e: st.error(f"Błąd CSV: {e}")

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
    # Aktualizujemy czas ostatniej aktywności gracza
    if role == "P1": server.p1_last_seen = time.time()
    elif role == "P2": server.p2_last_seen = time.time()

def check_disconnections(server):
    if server.mode == "solo" or server.status not in ["playing", "round_over"]: return
    now = time.time()
    # Tutaj limit jest większy (15s) niż limit usuwania pokoju (10s), 
    # ale to dotyczy sytuacji w trakcie meczu.
    if now - server.p1_last_seen > 15: server.status="disconnected"; server.disconnect_reason=f"{server.p1_name} rozłączył się!"
    elif now - server.p2_last_seen > 15: server.status="disconnected"; server.disconnect_reason=f"{server.p2_name} rozłączył się!"

def reset_game(server):
    server.mode="multi"; server.p1_name=None; server.p2_name=None; server.p1_score=0; server.p2_score=0
    server.status="lobby"; server.p1_locked=False; server.p2_locked=False; server.who_starts_next="P1"

# ==============================================================================
# 4. WIDOKI
# ==============================================================================

def view_main_menu():
    st.markdown("<h1 style='text-align: center;'>⚽ FOOTBALL QUIZ</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888;'>Wpisz nazwę pokoju, aby dołączyć</p>", unsafe_allow_html=True)
    
    st.markdown("<div class='room-box'>", unsafe_allow_html=True)
    
    c1, c2 = st.columns([3, 1])
    with c1:
        room_input = st.text_input("Nazwa pokoju:", placeholder="np. Stolik1", key="room_input_field")
    with c2:
        st.write(""); st.write("")
        if st.button("DOŁĄCZ 🚪", type="primary", use_container_width=True):
            if room_input:
                st.session_state.current_room_id = room_input
                st.rerun()
            else: st.error("Podaj nazwę!")
    st.markdown("</div>", unsafe_allow_html=True)

    # Lista aktywnych pokoi
    manager.cleanup_rooms()
    active_rooms = list(manager.rooms.keys())
    if active_rooms:
        st.caption(f"🟢 Aktywne pokoje ({len(active_rooms)}): {', '.join(active_rooms)}")
    else:
        st.caption("Brak aktywnych pokoi. Stwórz pierwszy!")
    
    # Odświeżanie listy pokoi co kilka sekund
    time.sleep(3)
    st.rerun()

def view_game_lobby(server):
    st.markdown(f"<h3 style='text-align: center;'>🚪 Pokój: {server.room_id}</h3>", unsafe_allow_html=True)
    
    if st.sidebar.button("🔙 Zmień Pokój"):
        del st.session_state.current_room_id; st.session_state.my_role = None; st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='player-box p1-box'>GOSPODARZ (P1)</div>", unsafe_allow_html=True)
        if server.p1_name: st.success(f"✅ {server.p1_name}")
        else:
            n = st.text_input("Nick P1", key="n1")
            cc1, cc2 = st.columns(2)
            if cc1.button("Host"): 
                if n: server.p1_name=n; server.mode="multi"; st.session_state.my_role="P1"; st.rerun()
            if cc2.button("Solo"): 
                if n: server.p1_name=n; server.mode="solo"; server.p2_name="CPU"; st.session_state.my_role="P1"; st.rerun()
    with c2:
        if server.mode=="solo": st.info("Tryb Solo")
        else:
            st.markdown("<div class='player-box p2-box'>GOŚĆ (P2)</div>", unsafe_allow_html=True)
            if server.p2_name: st.success(f"✅ {server.p2_name}")
            else:
                n = st.text_input("Nick P2", key="n2")
                if st.button("Dołącz"): 
                    if n: server.p2_name=n; server.mode="multi"; st.session_state.my_role="P2"; st.rerun()

    st.divider()
    
    if st.session_state.my_role == "P1":
        st.subheader("⚙️ Ustawienia")
        mode = st.selectbox("Wybierz kategorię:", list(GAME_MODES.keys()))
        csv_file, _ = GAME_MODES[mode]
        
        all_leagues = get_available_leagues(csv_file)
        sel_leagues = st.multiselect("Wybierz ligi:", all_leagues, default=all_leagues)
        use_top20 = st.checkbox("🏆 Tylko Top 20 (Ranking)", value=False)
        
        ready = (server.mode=="solo" and server.p1_name) or (server.mode=="multi" and server.p1_name and server.p2_name)
        
        if ready:
            if st.button("START MECZU 🚀", type="primary", use_container_width=True):
                if not sel_leagues: st.error("Wybierz ligę!")
                else:
                    load_images_filtered(server, csv_file, sel_leagues, use_top20)
                    server.active_category_name = mode
                    if not server.image_pool: st.error(f"Brak zdjęć! Sprawdź filtry.")
                    else: server.p1_last_seen=time.time(); server.p2_last_seen=time.time(); start_new_round(server); st.rerun()
        elif server.mode == "multi": 
            st.warning("Czekamy na drugiego gracza...")
            
    elif st.session_state.my_role == "P2": 
        st.info("Czekanie na hosta... (P1 konfiguruje grę)")
    
    time.sleep(1.5)
    st.rerun()

def view_playing(server):
    _, q_label = GAME_MODES.get(server.active_category_name, ("", "Wybierz:"))
    st.caption(f"Pokój: {server.room_id} | {server.active_category_name}")
    
    if server.mode=="solo": st.markdown(f"<div class='score-board' style='justify-content:center'>{server.p1_score}</div>", unsafe_allow_html=True)
    else: st.markdown(f"<div class='score-board'><span>{server.p1_name}: {server.p1_score}</span><span>VS</span><span>{server.p2_name}: {server.p2_score}</span></div>", unsafe_allow_html=True)
    
    if server.mode=="multi":
        if server.p1_locked: st.warning(f"{server.p1_name} zablokowany!")
        elif server.p2_locked: st.warning(f"{server.p2_name} zablokowany!")

    if server.current_image:
        try:
            r = requests.get(server.current_image); r.raise_for_status()
            st.image(Image.open(BytesIO(r.content)), use_container_width=True)
        except: st.error("Błąd ładowania obrazka")

    opts = sorted(list(set([x[0] for x in server.image_pool]))) if server.image_pool else []
    
    with st.form(f"gf_{server.room_id}_{server.round_id}_{server.input_reset_counter}"):
        guess = st.selectbox(q_label, [""]+opts)
        c1, c2 = st.columns([3,1])
        sub = c1.form_submit_button("ZGŁASZAM 🎯", type="primary", use_container_width=True)
        surr = c2.form_submit_button("🏳️", use_container_width=True)
        if st.session_state.my_role=="P1": st.form_submit_button("Zakończ Mecz", on_click=lambda: setattr(server,'status','finished'))

    role = st.session_state.my_role
    if sub and guess:
        locked = (role=="P1" and server.p1_locked) or (role=="P2" and server.p2_locked)
        if not locked:
            if handle_guess(server, guess): handle_win(server, role); st.rerun()
            else: 
                server.input_reset_counter += 1
                if role=="P1": server.p1_locked=True; server.p2_locked=False
                else: server.p2_locked=True; server.p1_locked=False
                st.toast("ŹLE!"); st.rerun()
        else: st.toast("Czekaj!")
    
    if surr: 
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
    if st.session_state.my_role=="P1" and st.sidebar.button("Zakończ"): server.status="finished"; st.rerun()
    
    col, txt = ("#555", "Nikt")
    if server.winner_last_round=="P1": col, txt = ("#1b5e20", server.p1_name)
    elif server.winner_last_round=="P2": col, txt = ("#0d47a1", server.p2_name)
    
    st.markdown(f"<div style='background:{col}; color:white; padding:10px; text-align:center'>Punkt: {txt}</div>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center'>{server.last_correct_answer}</h3>", unsafe_allow_html=True)
    
    if server.current_image:
        try: st.image(Image.open(BytesIO(requests.get(server.current_image).content)), use_container_width=True)
        except: pass

    st.divider()
    nxt = server.who_starts_next if server.mode=="multi" else "P1"
    if st.session_state.my_role == nxt:
        if st.button("DALEJ ➡️", type="primary", use_container_width=True): start_new_round(server); st.rerun()
    else: st.info(f"Czekaj na {nxt}..."); time.sleep(1); st.rerun()

def view_finished(server):
    st.title("KONIEC"); st.header(f"{server.p1_score} - {server.p2_score}")
    if st.button("LOBBY POKOJU 🔄"): reset_game(server); st.rerun()
    if st.button("ZMIEŃ POKÓJ 🚪"): del st.session_state.current_room_id; st.rerun()

def view_disconnected(server):
    st.error(f"🚨 WALKOWER! {server.disconnect_reason}")
    if st.button("WRÓĆ DO LOBBY 🏠", type="primary"): reset_game(server); st.rerun()
    time.sleep(2); st.rerun()

# ==============================================================================
# 5. MAIN
# ==============================================================================

def main():
    if 'current_room_id' not in st.session_state:
        view_main_menu()
    else:
        room_id = st.session_state.current_room_id
        
        # Jeśli pokój został usunięty w międzyczasie (bo nikt nie grał)
        # to wyrzucamy gracza do głównego menu
        if room_id not in manager.rooms and 'my_role' not in st.session_state:
             # Jeśli to dopiero wejście, manager stworzy pokój.
             # Ale jeśli pokój zniknął w trakcie gry, trzeba uważać.
             pass

        server = manager.get_room(room_id)
        
        if 'my_role' not in st.session_state: st.session_state.my_role = None
        
        # WAŻNE: Aktualizacja Heartbeatu dla RoomManagera
        if st.session_state.my_role:
            update_heartbeat(server, st.session_state.my_role)
        
        check_disconnections(server)

        if server.status == "lobby": view_game_lobby(server)
        elif server.status == "playing": view_playing(server)
        elif server.status == "round_over": view_round_over(server)
        elif server.status == "finished": view_finished(server)
        elif server.status == "disconnected": view_disconnected(server)

if __name__ == "__main__":
    main()















