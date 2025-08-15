from demoparser2 import DemoParser
import pandas as pd
import glob
import json
import os


pd.set_option("display.max_rows", 500)


def load_bonus_analysis_results():
    """
    Load all bonus analysis JSON files and extract the ticks
    """
    output_dir = "./bonus_analysis"
    bonus_files = glob.glob(os.path.join(output_dir, "*.json"))

    all_bonus_data = []

    for bonus_file in bonus_files:
        try:
            with open(bonus_file, "r") as f:
                data = json.load(f)

            if data["summary"]["total_occurrences"] > 0:
                for result in data["detailed_results"]:
                    all_bonus_data.append(
                        {
                            "demo_file": data["match_info"]["demo_file"],
                            "ct_team": data["match_info"]["ct_team"],
                            "t_team": data["match_info"]["t_team"],
                            "map": data["match_info"]["map"],
                            "bonus_tick": result["tick"],
                            "bonus_round": result["round_number"],
                            "bonus_amount": result["money_gain"],
                            "player_names": result["player_names"],
                        }
                    )
        except Exception as e:
            print(f"Error loading {bonus_file}: {e}")

    return all_bonus_data


def find_freeze_end_tick(parser, target_round):
    """
    Find the freeze time end tick for a specific round
    """
    try:
        freeze_events = parser.parse_event("round_freeze_end")
        if not freeze_events.empty:
            # Get all freeze end events and find the one for our target round
            freeze_events = freeze_events.sort_values("tick")

            # Parse round information to match freeze end with round number
            round_df = parser.parse_ticks(
                ["total_rounds_played"], ticks=freeze_events["tick"].tolist()
            )
            round_df = (
                round_df.groupby("tick")["total_rounds_played"].first().reset_index()
            )

            # Find the freeze end tick for our target round
            target_freeze = round_df[round_df["total_rounds_played"] == target_round]
            if not target_freeze.empty:
                return target_freeze.iloc[0]["tick"]

        return None
    except Exception as e:
        print(f"Error finding freeze end tick: {e}")
        return None


def get_equipment_at_tick(parser, tick):
    """
    Get equipment data for all CT players at a specific tick
    """
    try:
        # Parse player data at the specified tick - now include full inventory
        tick_data = parser.parse_ticks(
            [
                "user_id",
                "name",
                "team_name",
                "inventory",
                "current_equip_value",
                "balance",
            ],
            ticks=[tick],
        )

        # Filter for CT players (using team_name = 'CT' since that's the game-level team)
        ct_players = tick_data[tick_data["team_name"] == "CT"]

        if len(ct_players) != 5:
            print(f"    Warning: Found {len(ct_players)} CT players instead of 5")

        equipment_list = []
        for _, player in ct_players.iterrows():
            # Create equipment entry with full inventory
            equipment_entry = {
                "name": player["name"],
                "user_id": int(player["user_id"]),
                "inventory": (
                    player["inventory"] if isinstance(player["inventory"], list) else []
                ),
                "equipment_value": int(player["current_equip_value"]),
                "balance": int(player["balance"]),
                "round_number": None,  # Will be set by caller
            }
            equipment_list.append(equipment_entry)

        return equipment_list

    except Exception as e:
        print(f"    Error getting equipment at tick {tick}: {e}")
        return []


def analyze_equipment_after_bonus(bonus_data):
    """
    For each bonus event, find the equipment in the subsequent round
    """
    results = []

    # Group bonus events by demo file to avoid re-parsing
    demo_groups = {}
    for bonus_event in bonus_data:
        demo_file = bonus_event["demo_file"]
        if demo_file not in demo_groups:
            demo_groups[demo_file] = []
        demo_groups[demo_file].append(bonus_event)

    for demo_file, bonus_events in demo_groups.items():
        try:
            print(f"\n{'='*50}")
            print(f"Processing demo: {demo_file}")
            print(f"Bonus events to analyze: {len(bonus_events)}")
            print(f"{'='*50}")

            parser = DemoParser(demo_file)

            for bonus_event in bonus_events:
                try:
                    print(f"\nAnalyzing equipment for bonus event:")
                    print(f"  Bonus Round: {bonus_event['bonus_round']}")
                    print(f"  Bonus Tick: {bonus_event['bonus_tick']}")
                    print(f"  Bonus Amount: {bonus_event['bonus_amount']}")

                    # Find the subsequent round (bonus_round + 1)
                    target_round = bonus_event["bonus_round"] + 1

                    # Find freeze end tick for the subsequent round
                    freeze_end_tick = find_freeze_end_tick(parser, target_round)

                    if freeze_end_tick:
                        print(f"  Target Round: {target_round}")
                        print(f"  Freeze End Tick: {freeze_end_tick}")

                        # Get equipment data at freeze end for all CT players
                        equipment_data = get_equipment_at_tick(parser, freeze_end_tick)

                        # Set the round number for each player
                        if equipment_data:
                            for player in equipment_data:
                                player["round_number"] = target_round

                        if (
                            equipment_data and len(equipment_data) >= 4
                        ):  # At least 4 players found

                            bonus_amount = bonus_event["bonus_amount"]

                            # Filter: only include players where bonus amount > their individual balance
                            qualifying_players = []
                            filtered_players = []

                            for player in equipment_data:
                                if bonus_amount > player["balance"]:
                                    qualifying_players.append(player)
                                else:
                                    filtered_players.append(player)

                            # Only include the result if we have qualifying players
                            if qualifying_players:
                                # Calculate stats for reference
                                total_remaining_balance = sum(
                                    player["balance"] for player in equipment_data
                                )

                                result = {
                                    "bonus_event": bonus_event,
                                    "analysis_round": target_round,
                                    "freeze_end_tick": freeze_end_tick,
                                    "equipment_data": qualifying_players,  # Only include qualifying players
                                    "total_remaining_balance": total_remaining_balance,  # Keep for reference
                                    "qualifying_players_count": len(qualifying_players),
                                    "filtered_players_count": len(filtered_players),
                                }
                                results.append(result)

                                print(
                                    f"  Found equipment data for {len(equipment_data)} CT players"
                                )
                                print(
                                    f"  ✓ INCLUDED: {len(qualifying_players)} players qualify (bonus ${bonus_amount} > individual balance)"
                                )
                                print(f"    Qualifying players:")
                                for player in qualifying_players:
                                    inventory_str = (
                                        ", ".join(player["inventory"])
                                        if player["inventory"]
                                        else "No items"
                                    )
                                    print(
                                        f"      {player['name']}: Inventory=[{inventory_str}], Value=${player['equipment_value']}, Balance=${player['balance']} (${bonus_amount} > ${player['balance']})"
                                    )

                                if filtered_players:
                                    print(f"    Filtered out players:")
                                    for player in filtered_players:
                                        print(
                                            f"      {player['name']}: Balance=${player['balance']} (${bonus_amount} <= ${player['balance']})"
                                        )
                            else:
                                print(
                                    f"  ✗ FILTERED OUT: No players qualify (bonus ${bonus_amount} not greater than any individual balance)"
                                )
                                for player in equipment_data:
                                    print(
                                        f"    {player['name']}: Balance=${player['balance']} (${bonus_amount} <= ${player['balance']})"
                                    )
                        else:
                            found_count = len(equipment_data) if equipment_data else 0
                            print(
                                f"  Insufficient equipment data found for target round {target_round} (found {found_count} players)"
                            )
                    else:
                        print(
                            f"  Could not find freeze end tick for round {target_round}"
                        )

                except Exception as e:
                    print(f"  Error analyzing bonus event: {e}")

        except Exception as e:
            print(f"Error processing demo {demo_file}: {e}")

    return results


def generate_output_filename(demo_path, match_info, existing_filenames):
    """
    Generate output filename based on match information, handling duplicates
    """
    # Get the base filename without extension
    base_name = os.path.splitext(os.path.basename(demo_path))[0]

    # Clean team names (remove special characters that might cause file issues)
    ct_team = match_info["ct_team"].replace(" ", "_").replace("/", "_")
    t_team = match_info["t_team"].replace(" ", "_").replace("/", "_")
    map_name = match_info["map"].replace("de_", "")

    # Generate base filename
    if ct_team != "Unknown" and t_team != "Unknown":
        base_filename = f"{ct_team}_vs_{t_team}_{map_name}_ESL_equipment_analysis"
    else:
        # Fallback to original filename if team info not available
        base_filename = f"{base_name}_equipment_analysis"

    # Check for duplicates and add suffix if needed
    filename = f"{base_filename}.json"
    counter = 1

    while filename in existing_filenames:
        # Use last 8 characters of demo GUID as unique identifier
        guid_suffix = (
            match_info["demo_guid"][-8:]
            if match_info["demo_guid"] != "Unknown"
            else f"demo{counter}"
        )
        filename = f"{base_filename}_{guid_suffix}.json"
        counter += 1
        # Break if we've tried too many times to avoid infinite loop
        if counter > 10:
            break

    return filename


def save_equipment_analysis(equipment_results):
    """
    Save equipment analysis results to JSON files
    """
    output_dir = "./equipment_analysis"
    os.makedirs(output_dir, exist_ok=True)
    existing_filenames = set()  # Track existing filenames to handle duplicates

    # Group results by demo file
    demo_groups = {}
    for result in equipment_results:
        demo_file = result["bonus_event"]["demo_file"]
        if demo_file not in demo_groups:
            demo_groups[demo_file] = []
        demo_groups[demo_file].append(result)

    for demo_file, demo_results in demo_groups.items():
        try:
            # Get match info from first result and add demo_guid if available
            first_result = demo_results[0]
            match_info = {
                "demo_file": demo_file,
                "ct_team": first_result["bonus_event"]["ct_team"],
                "t_team": first_result["bonus_event"]["t_team"],
                "map": first_result["bonus_event"]["map"],
                "demo_guid": "Unknown",  # Default value - could be enhanced to parse from demo
            }

            # Generate filename using the same pattern as bonus_finder
            output_filename = generate_output_filename(
                demo_file, match_info, existing_filenames
            )
            existing_filenames.add(output_filename)  # Add to set to track usage
            output_path = os.path.join(output_dir, output_filename)

            # Create JSON structure
            json_output = {
                "match_info": match_info,
                "analysis_description": "Full inventory analysis for rounds following CT team bonus events (50-250 money gain) where bonus amount > individual player balance",
                "total_bonus_events_analyzed": len(demo_results),
                "equipment_analysis": [],
            }

            for result in demo_results:
                analysis_entry = {
                    "bonus_event_info": {
                        "bonus_round": int(result["bonus_event"]["bonus_round"]),
                        "bonus_tick": int(result["bonus_event"]["bonus_tick"]),
                        "bonus_amount": float(result["bonus_event"]["bonus_amount"]),
                    },
                    "equipment_round": int(result["analysis_round"]),
                    "freeze_end_tick": int(result["freeze_end_tick"]),
                    "total_remaining_balance": int(
                        result["total_remaining_balance"]
                    ),  # Add this field
                    "qualifying_players_count": int(
                        result["qualifying_players_count"]
                    ),  # Add player counts
                    "filtered_players_count": int(result["filtered_players_count"]),
                    "players_equipment": [],
                }

                # Convert equipment data to JSON-safe format
                for player in result["equipment_data"]:
                    player_data = {
                        "name": str(player["name"]),
                        "user_id": int(player["user_id"]),
                        "inventory": (
                            player["inventory"]
                            if isinstance(player["inventory"], list)
                            else []
                        ),
                        "equipment_value": int(player["equipment_value"]),
                        "balance": int(player["balance"]),
                        "round_number": int(player["round_number"]),
                    }
                    analysis_entry["players_equipment"].append(player_data)

                json_output["equipment_analysis"].append(analysis_entry)

            # Save to file
            with open(output_path, "w") as f:
                json.dump(json_output, f, indent=2)

            print(f"\nEquipment analysis saved to: {output_path}")

        except Exception as e:
            print(f"Error saving equipment analysis for {demo_file}: {e}")


def main():
    """
    Main function to run the equipment analysis
    """
    print("Loading bonus analysis results...")
    bonus_data = load_bonus_analysis_results()

    if not bonus_data:
        print("No bonus data found. Please run the bonus tracker first.")
        return

    print(f"Found {len(bonus_data)} bonus events to analyze")

    print("\nAnalyzing equipment purchases after bonus events...")
    equipment_results = analyze_equipment_after_bonus(bonus_data)

    if equipment_results:
        print(f"\nCompleted equipment analysis for {len(equipment_results)} events")
        save_equipment_analysis(equipment_results)

        print(f"\n{'='*60}")
        print(f"EQUIPMENT ANALYSIS COMPLETE")
        print(f"Total bonus events processed: {len(bonus_data)}")
        print(f"Successful equipment analyses: {len(equipment_results)}")
        print(f"Equipment analysis files saved in ./equipment_analysis/ directory")
        print(f"{'='*60}")
    else:
        print("No equipment data could be analyzed")


if __name__ == "__main__":
    main()
