def search_move_by_name(move):
    from main import move_collection
    move_name = move.lower().replace(' ', '-')
    result = move_collection.find_one({"name": move_name})
    return result