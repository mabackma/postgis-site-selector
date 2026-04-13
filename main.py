import json

from database import get_connection, get_nearest_infrastructures, save_substations

if __name__ == "__main__":
    conn = get_connection()
    cur = conn.cursor()

    bounding_box = "(60.1,24.8,60.3,25.2)"
    save_substations(cur, conn, bounding_box)

    coord_x, coord_y = (24.94, 60.17)
    infra_structures = get_nearest_infrastructures(cur, coord_x, coord_y)

    print(f"Nearest Infrastructure: {json.dumps(infra_structures, indent=2)}")

    cur.close()
    conn.close()
