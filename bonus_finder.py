from demoparser2 import DemoParser
import pandas as pd
import glob
import json
import os


pd.set_option("display.max_rows", 500)


def get_match_info(demo_path):
    """
    Extract match information from demo header and team data
    """
    parser = DemoParser(demo_path)

    # Get header information
    header = parser.parse_header()
    map_name = header.get("map_name", "Unknown")
    server_name = header.get("server_name", "Unknown")
    demo_guid = header.get("demo_version_guid", "Unknown")

    # Get team information
    try:
        team_df = parser.parse_ticks(
            ["team_name", "name", "team_clan_name"], ticks=[1000]
        )
        team_info = team_df.groupby("team_name").agg(
            {"team_clan_name": "first", "name": lambda x: list(x)}
        )

        ct_team = (
            team_info.loc["CT"]["team_clan_name"]
            if "CT" in team_info.index
            else "Unknown"
        )
        t_team = (
            team_info.loc["TERRORIST"]["team_clan_name"]
            if "TERRORIST" in team_info.index
            else "Unknown"
        )

    except Exception as e:
        ct_team = "Unknown"
        t_team = "Unknown"

    return {
        "map": map_name,
        "server": server_name,
        "ct_team": ct_team,
        "t_team": t_team,
        "demo_guid": demo_guid,
    }


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
        base_filename = f"{ct_team}_vs_{t_team}_{map_name}_ESL"
    else:
        # Fallback to original filename if team info not available
        base_filename = f"{base_name}_analysis"

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


def find_ct_money_gain_ticks(demo_path):
    """
    Find all ticks where all 5 CT players gain money simultaneously
    """
    print(f"Analyzing demo: {demo_path}")
    parser = DemoParser(demo_path)

    # Parse player data for all ticks - we need balance (money), team, player info, and round number
    df = parser.parse_ticks(
        ["balance", "team_name", "user_id", "name", "total_rounds_played"]
    )

    # Filter for CT players only
    ct_df = df[df["team_name"] == "CT"].copy()

    if ct_df.empty:
        print("No CT players found in demo")
        return []

    print(f"Found {ct_df['user_id'].nunique()} unique CT players")

    # Sort by user_id and tick to track money changes over time
    ct_df = ct_df.sort_values(["user_id", "tick"])

    # Calculate money gain for each player at each tick
    ct_df["balance_prev"] = ct_df.groupby("user_id")["balance"].shift(1)
    ct_df["money_gain"] = ct_df["balance"] - ct_df["balance_prev"]

    # Only consider ticks where we have previous money data (not the first tick for each player)
    ct_df = ct_df.dropna(subset=["balance_prev"])

    # Filter for money gains between 50 and 250
    ct_df = ct_df[(ct_df["money_gain"] >= 50) & (ct_df["money_gain"] <= 250)]

    # Group by tick and check conditions
    tick_analysis = (
        ct_df.groupby("tick")
        .agg(
            {
                "user_id": "count",  # Number of CT players at this tick
                "money_gain": [
                    "count",
                    lambda x: (x > 0).sum(),
                    lambda x: list(x),
                ],  # Count total, those with positive gain, and the values
                "name": lambda x: list(x),  # Player names for debugging
                "balance": lambda x: list(x),  # Current money amounts
                "total_rounds_played": "first",  # Round number (should be same for all players at same tick)
            }
        )
        .reset_index()
    )

    # Flatten column names
    tick_analysis.columns = [
        "tick",
        "ct_player_count",
        "players_with_data",
        "players_with_gain",
        "money_gains",
        "player_names",
        "money_amounts",
        "round_number",
    ]

    # Find ticks where all 5 CT players gained money
    valid_ticks = tick_analysis[
        (tick_analysis["ct_player_count"] == 5)  # Exactly 5 CT players
        & (tick_analysis["players_with_gain"] == 5)  # All 5 gained money
    ]

    print(
        f"Found {len(valid_ticks)} ticks where all 5 CT players gained money (50-250 range)"
    )

    return valid_ticks


def analyze_all_demos():
    """
    Analyze all demo files for CT money gain patterns (50-250 range) and output to JSON files
    """
    demo_files = glob.glob("./demos/*.dem")
    all_results = []
    existing_filenames = set()  # Track existing filenames to handle duplicates

    # Create output directory if it doesn't exist
    output_dir = "./bonus_analysis"
    os.makedirs(output_dir, exist_ok=True)

    for demo_file in demo_files:
        try:
            # Get match information first
            match_info = get_match_info(demo_file)
            print(f"\n{'='*60}")
            print(f"DEMO: {demo_file}")
            print(f"Match: {match_info['ct_team']} vs {match_info['t_team']}")
            print(f"Map: {match_info['map']}")
            print(f"Server: {match_info['server']}")
            print(f"Demo GUID: {match_info['demo_guid']}")
            print(f"{'='*60}")

            results = find_ct_money_gain_ticks(demo_file)

            # Generate output filename with duplicate handling
            output_filename = generate_output_filename(
                demo_file, match_info, existing_filenames
            )
            existing_filenames.add(output_filename)  # Add to set to track usage
            output_path = os.path.join(output_dir, output_filename)

            if not results.empty:
                # Convert results to JSON-serializable format
                tick_gain_pairs = []
                detailed_results = []

                for _, row in results.iterrows():
                    # Since all players have the same gain, just take the first one
                    gain_amount = float(row["money_gains"][0])
                    tick_gain_pairs.append([int(row["tick"]), gain_amount])

                    # Detailed result for JSON
                    detailed_results.append(
                        {
                            "tick": int(row["tick"]),
                            "round_number": int(row["round_number"]),
                            "money_gain": gain_amount,
                            "player_names": row["player_names"],
                            "player_balances": [float(x) for x in row["money_amounts"]],
                        }
                    )

                # Create JSON output
                json_output = {
                    "match_info": {
                        "demo_file": demo_file,
                        "ct_team": match_info["ct_team"],
                        "t_team": match_info["t_team"],
                        "map": match_info["map"],
                        "server": match_info["server"],
                        "demo_guid": match_info["demo_guid"],
                    },
                    "analysis_criteria": {
                        "money_gain_range": [50, 250],
                        "description": "Ticks where all 5 CT players gained money simultaneously",
                    },
                    "summary": {
                        "total_occurrences": len(results),
                        "tick_gain_pairs": tick_gain_pairs,
                    },
                    "detailed_results": detailed_results,
                }

                # Write to JSON file
                with open(output_path, "w") as f:
                    json.dump(json_output, f, indent=2)

                print(f"\nResults saved to: {output_path}")
                print(f"Total occurrences: {len(results)}")
                print(f"Tick-gain pairs:")
                for tick, gain in tick_gain_pairs:
                    print(f"  ({tick}, {gain})")

                # Add to combined results for summary
                results["demo_file"] = demo_file
                results["ct_team"] = match_info["ct_team"]
                results["t_team"] = match_info["t_team"]
                results["map_name"] = match_info["map"]
                all_results.append(results)

            else:
                # Create JSON even if no results found
                json_output = {
                    "match_info": {
                        "demo_file": demo_file,
                        "ct_team": match_info["ct_team"],
                        "t_team": match_info["t_team"],
                        "map": match_info["map"],
                        "server": match_info["server"],
                        "demo_guid": match_info["demo_guid"],
                    },
                    "analysis_criteria": {
                        "money_gain_range": [50, 250],
                        "description": "Ticks where all 5 CT players gained money simultaneously",
                    },
                    "summary": {"total_occurrences": 0, "tick_gain_pairs": []},
                    "detailed_results": [],
                }

                with open(output_path, "w") as f:
                    json.dump(json_output, f, indent=2)

                print(f"No results found - empty analysis saved to: {output_path}")

        except Exception as e:
            print(f"Error analyzing {demo_file}: {e}")

    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE")
    print(f"Total demos analyzed: {len(demo_files)}")
    print(f"JSON files created in ./output/ directory")
    print(f"{'='*60}")

    return len(demo_files)


if __name__ == "__main__":
    results = analyze_all_demos()
