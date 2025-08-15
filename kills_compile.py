from demoparser2 import DemoParser
import pandas as pd
import glob
import json
import os


pd.set_option("display.max_rows", 500)


def load_equipment_analysis_results():
    """
    Load all equipment analysis JSON files
    """
    output_dir = "./equipment_analysis"
    equipment_files = glob.glob(os.path.join(output_dir, "*.json"))

    all_equipment_data = []

    for equipment_file in equipment_files:
        try:
            with open(equipment_file, "r") as f:
                data = json.load(f)

            for analysis in data["equipment_analysis"]:
                equipment_round = analysis["equipment_round"]
                freeze_end_tick = analysis["freeze_end_tick"]

                for player_equipment in analysis["players_equipment"]:
                    all_equipment_data.append(
                        {
                            "demo_file": data["match_info"]["demo_file"],
                            "ct_team": data["match_info"]["ct_team"],
                            "t_team": data["match_info"]["t_team"],
                            "map": data["match_info"]["map"],
                            "round_number": equipment_round,
                            "freeze_end_tick": freeze_end_tick,
                            "player_name": player_equipment["name"],
                            "user_id": player_equipment["user_id"],
                            "inventory": player_equipment["inventory"],
                            "equipment_value": player_equipment["equipment_value"],
                            "balance": player_equipment["balance"],
                            "bonus_info": analysis["bonus_event_info"],
                        }
                    )

        except Exception as e:
            print(f"Error loading {equipment_file}: {e}")

    return all_equipment_data


def normalize_weapon_name(weapon_name):
    """
    Normalize weapon names to match between inventory and kill events
    Some weapons might have different naming conventions
    """
    weapon_mapping = {
        "USP-S": "usp_silencer",
        "M4A4": "m4a1",
        "M4A1-S": "m4a1_silencer",
        "AK-47": "ak47",
        "AWP": "awp",
        "Desert Eagle": "deagle",
        "Glock-18": "glock",
        "P250": "p250",
        "Five-SeveN": "fiveseven",
        "Tec-9": "tec9",
        "CZ75-Auto": "cz75a",
        "Dual Berettas": "elite",
        "P2000": "hkp2000",
        "R8 Revolver": "revolver",
        "Nova": "nova",
        "XM1014": "xm1014",
        "Sawed-Off": "sawedoff",
        "MAG-7": "mag7",
        "M249": "m249",
        "Negev": "negev",
        "MAC-10": "mac10",
        "MP9": "mp9",
        "MP7": "mp7",
        "UMP-45": "ump45",
        "P90": "p90",
        "PP-Bizon": "bizon",
        "MP5-SD": "mp5sd",
        "FAMAS": "famas",
        "Galil AR": "galilar",
        "SSG 08": "ssg08",
        "SG 553": "sg556",
        "AUG": "aug",
        "G3SG1": "g3sg1",
        "SCAR-20": "scar20",
        "HE Grenade": "hegrenade",
        "Flashbang": "flashbang",
        "Smoke Grenade": "smokegrenade",
        "Incendiary Grenade": "incgrenade",
        "Molotov": "molotov",
        "Decoy Grenade": "decoy",
        # Knives are typically just "knife" in kill events
        "Butterfly Knife": "knife",
        "Karambit": "knife",
        "Bayonet": "knife",
        "M9 Bayonet": "knife",
        "Huntsman Knife": "knife",
        "Falchion Knife": "knife",
        "Bowie Knife": "knife",
        "Shadow Daggers": "knife",
        "Gut Knife": "knife",
        "Flip Knife": "knife",
    }

    return weapon_mapping.get(
        weapon_name, weapon_name.lower().replace("-", "").replace(" ", "")
    )


def get_round_bounds(parser, round_number):
    """
    Get the start and end ticks for a specific round
    """
    try:
        # Parse round start events
        round_start_events = parser.parse_event("round_start")

        if not round_start_events.empty:
            round_start_events = round_start_events.sort_values("tick")

            # Get round information to match ticks with round numbers
            round_df = parser.parse_ticks(
                ["total_rounds_played"], ticks=round_start_events["tick"].tolist()
            )
            round_df = (
                round_df.groupby("tick")["total_rounds_played"].first().reset_index()
            )

            # Find start tick for target round
            target_round_start = round_df[
                round_df["total_rounds_played"] == round_number
            ]
            if target_round_start.empty:
                return None, None

            start_tick = target_round_start.iloc[0]["tick"]

            # Find end tick (start of next round or end of demo)
            next_round_start = round_df[
                round_df["total_rounds_played"] == round_number + 1
            ]
            if not next_round_start.empty:
                end_tick = next_round_start.iloc[0]["tick"]
            else:
                # If no next round, use a large tick number
                end_tick = start_tick + 100000

            return start_tick, end_tick

    except Exception as e:
        print(f"Error finding round bounds for round {round_number}: {e}")
        return None, None


def analyze_kills_with_purchased_weapons(equipment_data):
    """
    For each player's equipment, find kills they made with those weapons in the same round
    """
    results = []

    # Group equipment data by demo file to avoid re-parsing
    demo_groups = {}
    for equipment_entry in equipment_data:
        demo_file = equipment_entry["demo_file"]
        if demo_file not in demo_groups:
            demo_groups[demo_file] = []
        demo_groups[demo_file].append(equipment_entry)

    for demo_file, equipment_entries in demo_groups.items():
        try:
            print(f"\n{'='*50}")
            print(f"Processing demo: {demo_file}")
            print(f"Equipment entries to analyze: {len(equipment_entries)}")
            print(f"{'='*50}")

            parser = DemoParser(demo_file)

            # Parse all player death events for this demo
            death_events = parser.parse_event(
                "player_death",
                player=["user_id", "name", "X", "Y", "Z", "team_name"],
                other=[
                    "total_rounds_played",
                    "attacker_user_id",
                    "attacker_name",
                    "attacker_X",
                    "attacker_Y",
                    "attacker_Z",
                    "attacker_team_name",
                    "weapon",
                ],
            )

            if death_events.empty:
                print("No death events found in demo")
                continue

            print(f"Found {len(death_events)} death events")

            for equipment_entry in equipment_entries:
                try:
                    round_number = equipment_entry["round_number"]
                    player_name = equipment_entry["player_name"]
                    user_id = equipment_entry["user_id"]
                    inventory = equipment_entry["inventory"]

                    print(
                        f"\nAnalyzing kills for {player_name} (ID: {user_id}) in round {round_number}"
                    )
                    print(f"  Inventory: {inventory}")

                    # Filter death events for this round and this attacker
                    round_kills = death_events[
                        (death_events["total_rounds_played"] == round_number)
                        & (death_events["attacker_user_id"] == user_id)
                    ]

                    if round_kills.empty:
                        print(
                            f"  No kills found for {player_name} in round {round_number}"
                        )
                        continue

                    print(
                        f"  Found {len(round_kills)} kills by {player_name} in round {round_number}"
                    )

                    # Normalize inventory weapon names
                    normalized_inventory = [
                        normalize_weapon_name(weapon) for weapon in inventory
                    ]

                    kills_with_purchased_weapons = []

                    for _, kill in round_kills.iterrows():
                        kill_weapon = normalize_weapon_name(kill["weapon"])

                        # Check if the kill weapon matches any weapon in inventory
                        weapon_in_inventory = False
                        original_weapon_name = None

                        for i, norm_weapon in enumerate(normalized_inventory):
                            if (
                                norm_weapon == kill_weapon
                                or kill_weapon in norm_weapon
                                or norm_weapon in kill_weapon
                            ):
                                weapon_in_inventory = True
                                original_weapon_name = inventory[i]
                                break

                        if weapon_in_inventory:
                            kill_data = {
                                "tick": int(kill["tick"]),
                                "weapon_used": kill["weapon"],
                                "weapon_from_inventory": original_weapon_name,
                                "victim_name": kill["user_name"],
                                "victim_user_id": int(kill["user_user_id"]),
                                "victim_team": kill["user_team_name"],
                                "victim_location": {
                                    "X": float(kill["user_X"]),
                                    "Y": float(kill["user_Y"]),
                                    "Z": float(kill["user_Z"]),
                                },
                                "attacker_location": {
                                    "X": float(kill["attacker_X"]),
                                    "Y": float(kill["attacker_Y"]),
                                    "Z": float(kill["attacker_Z"]),
                                },
                            }
                            kills_with_purchased_weapons.append(kill_data)

                            print(
                                f"    Kill with {original_weapon_name} -> {kill['user_name']} at tick {kill['tick']}"
                            )

                    if kills_with_purchased_weapons:
                        result = {
                            "equipment_info": equipment_entry,
                            "kills_analysis": {
                                "total_kills_in_round": len(round_kills),
                                "kills_with_purchased_weapons": len(
                                    kills_with_purchased_weapons
                                ),
                                "kill_details": kills_with_purchased_weapons,
                            },
                        }
                        results.append(result)

                        print(
                            f"  Successfully analyzed {len(kills_with_purchased_weapons)} kills with purchased weapons"
                        )
                    else:
                        print(f"  No kills found with weapons from inventory")

                except Exception as e:
                    print(f"  Error analyzing equipment entry: {e}")

        except Exception as e:
            print(f"Error processing demo {demo_file}: {e}")

    return results


def generate_kills_output_filename(demo_path, match_info, existing_filenames):
    """
    Generate output filename for kills analysis
    """
    # Get the base filename without extension
    base_name = os.path.splitext(os.path.basename(demo_path))[0]

    # Clean team names
    ct_team = match_info["ct_team"].replace(" ", "_").replace("/", "_")
    t_team = match_info["t_team"].replace(" ", "_").replace("/", "_")
    map_name = match_info["map"].replace("de_", "")

    # Generate base filename
    if ct_team != "Unknown" and t_team != "Unknown":
        base_filename = f"{ct_team}_vs_{t_team}_{map_name}_ESL_kills_analysis"
    else:
        base_filename = f"{base_name}_kills_analysis"

    # Check for duplicates and add suffix if needed
    filename = f"{base_filename}.json"
    counter = 1

    while filename in existing_filenames:
        guid_suffix = f"demo{counter}"
        filename = f"{base_filename}_{guid_suffix}.json"
        counter += 1
        if counter > 10:
            break

    return filename


def save_kills_analysis(kills_results):
    """
    Save kills analysis results to JSON files
    """
    output_dir = "./kills_analysis"
    os.makedirs(output_dir, exist_ok=True)
    existing_filenames = set()

    # Group results by demo file
    demo_groups = {}
    for result in kills_results:
        demo_file = result["equipment_info"]["demo_file"]
        if demo_file not in demo_groups:
            demo_groups[demo_file] = []
        demo_groups[demo_file].append(result)

    for demo_file, demo_results in demo_groups.items():
        try:
            # Get match info from first result
            first_result = demo_results[0]
            match_info = {
                "demo_file": demo_file,
                "ct_team": first_result["equipment_info"]["ct_team"],
                "t_team": first_result["equipment_info"]["t_team"],
                "map": first_result["equipment_info"]["map"],
            }

            # Generate filename
            output_filename = generate_kills_output_filename(
                demo_file, match_info, existing_filenames
            )
            existing_filenames.add(output_filename)
            output_path = os.path.join(output_dir, output_filename)

            # Calculate summary statistics
            total_players_analyzed = len(demo_results)
            total_kills_with_purchased_weapons = sum(
                result["kills_analysis"]["kills_with_purchased_weapons"]
                for result in demo_results
            )

            # Create JSON structure
            json_output = {
                "match_info": match_info,
                "analysis_description": "Analysis of kills made with weapons purchased after CT team bonus events",
                "summary": {
                    "total_players_analyzed": total_players_analyzed,
                    "total_kills_with_purchased_weapons": total_kills_with_purchased_weapons,
                },
                "player_analyses": [],
            }

            for result in demo_results:
                player_analysis = {
                    "player_info": {
                        "name": result["equipment_info"]["player_name"],
                        "user_id": result["equipment_info"]["user_id"],
                        "round_number": result["equipment_info"]["round_number"],
                        "inventory": result["equipment_info"]["inventory"],
                        "equipment_value": result["equipment_info"]["equipment_value"],
                        "balance": result["equipment_info"]["balance"],
                    },
                    "bonus_event_info": result["equipment_info"]["bonus_info"],
                    "kills_analysis": result["kills_analysis"],
                }
                json_output["player_analyses"].append(player_analysis)

            # Save to file
            with open(output_path, "w") as f:
                json.dump(json_output, f, indent=2)

            print(f"\nKills analysis saved to: {output_path}")

        except Exception as e:
            print(f"Error saving kills analysis for {demo_file}: {e}")


def main():
    """
    Main function to run the kills analysis
    """
    print("Loading equipment analysis results...")
    equipment_data = load_equipment_analysis_results()

    if not equipment_data:
        print("No equipment data found. Please run the equipment finder first.")
        return

    print(f"Found {len(equipment_data)} equipment entries to analyze")

    print("\nAnalyzing kills made with purchased weapons...")
    kills_results = analyze_kills_with_purchased_weapons(equipment_data)

    if kills_results:
        print(
            f"\nCompleted kills analysis for {len(kills_results)} player equipment entries"
        )
        save_kills_analysis(kills_results)

        print(f"\n{'='*60}")
        print(f"KILLS ANALYSIS COMPLETE")
        print(f"Total equipment entries processed: {len(equipment_data)}")
        print(f"Successful kills analyses: {len(kills_results)}")
        print(f"Kills analysis files saved in ./kills_analysis/ directory")
        print(f"{'='*60}")
    else:
        print("No kills data could be analyzed")


if __name__ == "__main__":
    main()
