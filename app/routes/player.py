from fastapi import APIRouter

router = APIRouter()

players_db = {}

@router.post("/join")
async def join_game(data: dict):

    print("PLAYER RECEIVED =", data)

    pin = data["pin"]
    username = data["username"]

    if pin not in players_db:
        players_db[pin] = []

    players_db[pin].append({
        "username": username
    })

    print("PLAYERS DB =", players_db)

    return {
        "message": "Player joined"
    }


@router.get("/{pin}")
async def get_players(pin: str):

    print("GET PLAYERS =", pin)

    return players_db.get(pin, [])