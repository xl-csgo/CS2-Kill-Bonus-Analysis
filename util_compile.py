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
    Normalize weapon names to match between inventory and damage events
    """
    weapon_mapping = {
        "HE Grenade": "hegrenade",
        "High Explosive Grenade": "hegrenade",
        "Flashbang": "flashbang",
        "Smoke Grenade": "smokegrenade",
        "Incendiary Grenade": "incgrenade",
        "Molotov": "molotov",
        "Decoy Grenade": "decoy",
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


def analyze_utility_impact_with_purchased_items(equipment_data):
    """
    For each player's equipment, find utility impact they made with purchased utility in the same round
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

            # Parse player hurt events for HE and fire damage
            hurt_events = parser.parse_event(
                "player_hurt",
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
                    "dmg_health",
                    "dmg_armor",
                ],
            )

            # Parse flashbang detonate events
            flashbang_events = parser.parse_event(
                "flashbang_detonate",
                other=[
                    "total_rounds_played",
                    "userid",
                    "x",
                    "y",
                    "z",
                ],
            )

            # Parse player blind events (for flash assists)
            player_blind_events = parser.parse_event(
                "player_blind",
                player=["user_id", "name", "team_name"],
                other=[
                    "total_rounds_played",
                    "attacker_user_id",
                    "attacker_name",
                    "attacker_team_name",
                    "blind_duration",
                ],
            )

            # Convert to DataFrame if they're not already (handle empty results)
            if not isinstance(hurt_events, pd.DataFrame):
                hurt_events = pd.DataFrame()
            if not isinstance(flashbang_events, pd.DataFrame):
                flashbang_events = pd.DataFrame()
            if not isinstance(player_blind_events, pd.DataFrame):
                player_blind_events = pd.DataFrame()

            print(f"Found {len(hurt_events)} player hurt events")
            print(f"Found {len(flashbang_events)} flashbang detonate events")
            print(f"Found {len(player_blind_events)} player blind events")

            for equipment_entry in equipment_entries:
                try:
                    round_number = equipment_entry["round_number"]
                    player_name = equipment_entry["player_name"]
                    user_id = equipment_entry["user_id"]
                    inventory = equipment_entry["inventory"]

                    print(
                        f"\nAnalyzing utility impact for {player_name} (ID: {user_id}) in round {round_number}"
                    )
                    print(f"  Inventory: {inventory}")

                    # Check if player has any utility in inventory
                    utility_items = []
                    for item in inventory:
                        normalized_item = normalize_weapon_name(item)
                        if normalized_item in [
                            "hegrenade",
                            "incgrenade",
                            "molotov",
                            "flashbang",
                        ]:
                            utility_items.append(item)
                        elif "grenade" in item.lower():  # Also include HE grenades
                            utility_items.append(item)

                    if not utility_items:
                        print(f"  No utility items found in inventory")
                        continue

                    print(f"  Utility items in inventory: {utility_items}")

                    # Analyze HE/Incendiary damage
                    utility_damage = []
                    if not hurt_events.empty:
                        round_damage = hurt_events[
                            (hurt_events["total_rounds_played"] == round_number)
                            & (hurt_events["attacker_user_id"] == user_id)
                        ]

                        for _, damage_event in round_damage.iterrows():
                            weapon_used = damage_event["weapon"]
                            normalized_weapon = normalize_weapon_name(weapon_used)

                            # Check if damage was from utility in inventory
                            if normalized_weapon in [
                                normalize_weapon_name(item) for item in utility_items
                            ]:
                                if normalized_weapon in [
                                    "hegrenade",
                                    "incgrenade",
                                    "molotov",
                                ]:
                                    damage_data = {
                                        "tick": int(damage_event["tick"]),
                                        "weapon_used": weapon_used,
                                        "victim_name": damage_event["user_name"],
                                        "victim_user_id": int(
                                            damage_event["user_user_id"]
                                        ),
                                        "victim_team": damage_event["user_team_name"],
                                        "health_damage": int(
                                            damage_event["dmg_health"]
                                        ),
                                        "armor_damage": int(damage_event["dmg_armor"]),
                                        "total_damage": int(damage_event["dmg_health"])
                                        + int(damage_event["dmg_armor"]),
                                        "victim_location": {
                                            "X": float(damage_event["user_X"]),
                                            "Y": float(damage_event["user_Y"]),
                                            "Z": float(damage_event["user_Z"]),
                                        },
                                        "attacker_location": {
                                            "X": float(damage_event["attacker_X"]),
                                            "Y": float(damage_event["attacker_Y"]),
                                            "Z": float(damage_event["attacker_Z"]),
                                        },
                                    }
                                    utility_damage.append(damage_data)

                    # Analyze flash assists
                    flash_assists = []
                    if not player_blind_events.empty and "flashbang" in [
                        normalize_weapon_name(item) for item in utility_items
                    ]:
                        round_blinds = player_blind_events[
                            (player_blind_events["total_rounds_played"] == round_number)
                            & (player_blind_events["attacker_user_id"] == user_id)
                            & (
                                player_blind_events["user_team_name"]
                                != player_blind_events["attacker_team_name"]
                            )  # Only enemy blinds
                        ]

                        for _, blind_event in round_blinds.iterrows():
                            flash_data = {
                                "tick": int(blind_event["tick"]),
                                "victim_name": blind_event["user_name"],
                                "victim_user_id": int(blind_event["user_user_id"]),
                                "victim_team": blind_event["user_team_name"],
                                "blind_duration": float(blind_event["blind_duration"]),
                            }
                            flash_assists.append(flash_data)

                    # Calculate summary statistics
                    total_utility_damage = sum(
                        damage["total_damage"] for damage in utility_damage
                    )
                    total_enemies_damaged = len(
                        set(damage["victim_user_id"] for damage in utility_damage)
                    )
                    total_enemies_flashed = len(flash_assists)

                    if utility_damage or flash_assists:
                        result = {
                            "equipment_info": equipment_entry,
                            "utility_analysis": {
                                "utility_items_in_inventory": utility_items,
                                "total_utility_damage": total_utility_damage,
                                "total_enemies_damaged": total_enemies_damaged,
                                "total_enemies_flashed": total_enemies_flashed,
                                "utility_damage_events": utility_damage,
                                "flash_assist_events": flash_assists,
                            },
                        }
                        results.append(result)

                        print(f"  Utility impact found:")
                        print(f"    Total damage: {total_utility_damage}")
                        print(f"    Enemies damaged: {total_enemies_damaged}")
                        print(f"    Enemies flashed: {total_enemies_flashed}")
                    else:
                        print(f"  No utility impact found with purchased items")

                except Exception as e:
                    print(f"  Error analyzing equipment entry: {e}")

        except Exception as e:
            print(f"Error processing demo {demo_file}: {e}")

    return results


def generate_utility_output_filename(demo_path, match_info, existing_filenames):
    """
    Generate output filename for utility analysis
    """
    # Get the base filename without extension
    base_name = os.path.splitext(os.path.basename(demo_path))[0]

    # Clean team names
    ct_team = match_info["ct_team"].replace(" ", "_").replace("/", "_")
    t_team = match_info["t_team"].replace(" ", "_").replace("/", "_")
    map_name = match_info["map"].replace("de_", "")

    # Generate base filename
    if ct_team != "Unknown" and t_team != "Unknown":
        base_filename = f"{ct_team}_vs_{t_team}_{map_name}_ESL_utility_analysis"
    else:
        base_filename = f"{base_name}_utility_analysis"

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


def save_utility_analysis(utility_results):
    """
    Save utility analysis results to JSON files
    """
    output_dir = "./utility_analysis"
    os.makedirs(output_dir, exist_ok=True)
    existing_filenames = set()

    # Group results by demo file
    demo_groups = {}
    for result in utility_results:
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
            output_filename = generate_utility_output_filename(
                demo_file, match_info, existing_filenames
            )
            existing_filenames.add(output_filename)
            output_path = os.path.join(output_dir, output_filename)

            # Calculate summary statistics
            total_players_analyzed = len(demo_results)
            total_utility_damage = sum(
                result["utility_analysis"]["total_utility_damage"]
                for result in demo_results
            )
            total_enemies_damaged = sum(
                result["utility_analysis"]["total_enemies_damaged"]
                for result in demo_results
            )
            total_enemies_flashed = sum(
                result["utility_analysis"]["total_enemies_flashed"]
                for result in demo_results
            )

            # Create JSON structure
            json_output = {
                "match_info": match_info,
                "analysis_description": "Analysis of utility impact made with items purchased after CT team bonus events",
                "summary": {
                    "total_players_analyzed": total_players_analyzed,
                    "total_utility_damage": total_utility_damage,
                    "total_enemies_damaged": total_enemies_damaged,
                    "total_enemies_flashed": total_enemies_flashed,
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
                    "utility_analysis": result["utility_analysis"],
                }
                json_output["player_analyses"].append(player_analysis)

            # Save to file
            with open(output_path, "w") as f:
                json.dump(json_output, f, indent=2)

            print(f"\nUtility analysis saved to: {output_path}")

        except Exception as e:
            print(f"Error saving utility analysis for {demo_file}: {e}")


def main():
    """
    Main function to run the utility analysis
    """
    print("Loading equipment analysis results...")
    equipment_data = load_equipment_analysis_results()

    if not equipment_data:
        print("No equipment data found. Please run the equipment finder first.")
        return

    print(f"Found {len(equipment_data)} equipment entries to analyze")

    print("\nAnalyzing utility impact with purchased items...")
    utility_results = analyze_utility_impact_with_purchased_items(equipment_data)

    if utility_results:
        print(
            f"\nCompleted utility analysis for {len(utility_results)} player equipment entries"
        )
        save_utility_analysis(utility_results)

        print(f"\n{'='*60}")
        print(f"UTILITY ANALYSIS COMPLETE")
        print(f"Total equipment entries processed: {len(equipment_data)}")
        print(f"Successful utility analyses: {len(utility_results)}")
        print(f"Utility analysis files saved in ./utility_analysis/ directory")
        print(f"{'='*60}")
    else:
        print("No utility data could be analyzed")


if __name__ == "__main__":
    main()
