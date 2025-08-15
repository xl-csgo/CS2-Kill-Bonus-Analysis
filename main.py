#!/usr/bin/env python3
"""
CS2 Kill Bonus Analysis - Main Orchestrator

This script runs all analysis components in the correct order:
1. Bonus analysis (bonus_finder.py)
2. Equipment analysis (equipment_finder.py)
3. Kills analysis (kills_compile.py)
4. Utility analysis (util_compile.py)
5. Generate combined final output

Usage: python main.py
"""

import os
import sys
import json
import glob
import time
from datetime import datetime

# Import all analysis modules
import bonus_finder
import equipment_finder
import kills_compile
import util_compile


def print_banner(title):
    """Print a formatted banner for each analysis phase"""
    banner_width = 80
    print("=" * banner_width)
    print(f"{title:^{banner_width}}")
    print("=" * banner_width)


def print_phase_complete(phase_name, duration):
    """Print completion message with timing"""
    print(f"\n✅ {phase_name} completed in {duration:.2f} seconds")
    print("-" * 60)


def load_all_analysis_results():
    """Load results from all analysis phases"""
    results = {
        "bonus_analysis": {},
        "equipment_analysis": {},
        "kills_analysis": {},
        "utility_analysis": {},
    }

    # Load bonus analysis results
    bonus_files = glob.glob("./bonus_analysis/*.json")
    for file_path in bonus_files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                filename = os.path.basename(file_path)
                results["bonus_analysis"][filename] = data
        except Exception as e:
            print(f"Error loading bonus analysis file {file_path}: {e}")

    # Load equipment analysis results
    equipment_files = glob.glob("./equipment_analysis/*.json")
    for file_path in equipment_files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                filename = os.path.basename(file_path)
                results["equipment_analysis"][filename] = data
        except Exception as e:
            print(f"Error loading equipment analysis file {file_path}: {e}")

    # Load kills analysis results
    kills_files = glob.glob("./kills_analysis/*.json")
    for file_path in kills_files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                filename = os.path.basename(file_path)
                results["kills_analysis"][filename] = data
        except Exception as e:
            print(f"Error loading kills analysis file {file_path}: {e}")

    # Load utility analysis results
    utility_files = glob.glob("./utility_analysis/*.json")
    for file_path in utility_files:
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                filename = os.path.basename(file_path)
                results["utility_analysis"][filename] = data
        except Exception as e:
            print(f"Error loading utility analysis file {file_path}: {e}")

    return results


def generate_combined_summary(all_results):
    """Generate high-level summary statistics across all analyses"""
    summary = {
        "analysis_overview": {
            "total_demos_analyzed": 0,
            "total_bonus_events": 0,
            "total_equipment_purchases": 0,
            "total_kills_with_purchased_weapons": 0,
            "total_utility_impact_events": 0,
        },
        "demo_breakdown": {},
        "team_statistics": {},
        "map_statistics": {},
    }

    # Collect demo information and statistics
    demos_processed = set()
    team_stats = {}
    map_stats = {}

    # Process bonus analysis data
    for filename, data in all_results["bonus_analysis"].items():
        match_info = data["match_info"]
        demo_file = match_info["demo_file"]
        ct_team = match_info["ct_team"]
        t_team = match_info["t_team"]
        map_name = match_info["map"]

        demos_processed.add(demo_file)

        # Initialize demo breakdown entry
        if demo_file not in summary["demo_breakdown"]:
            summary["demo_breakdown"][demo_file] = {
                "match_info": match_info,
                "bonus_events": 0,
                "equipment_purchases": 0,
                "kills_with_purchased_weapons": 0,
                "utility_impact_events": 0,
            }

        summary["demo_breakdown"][demo_file]["bonus_events"] = data["summary"][
            "total_occurrences"
        ]
        summary["analysis_overview"]["total_bonus_events"] += data["summary"][
            "total_occurrences"
        ]

        # Team statistics
        if ct_team not in team_stats:
            team_stats[ct_team] = {
                "bonus_events": 0,
                "equipment_purchases": 0,
                "kills": 0,
                "utility_impact": 0,
            }
        team_stats[ct_team]["bonus_events"] += data["summary"]["total_occurrences"]

        # Map statistics
        if map_name not in map_stats:
            map_stats[map_name] = {
                "bonus_events": 0,
                "equipment_purchases": 0,
                "kills": 0,
                "utility_impact": 0,
            }
        map_stats[map_name]["bonus_events"] += data["summary"]["total_occurrences"]

    # Process equipment analysis data
    for filename, data in all_results["equipment_analysis"].items():
        demo_file = data["match_info"]["demo_file"]
        ct_team = data["match_info"]["ct_team"]
        map_name = data["match_info"]["map"]

        equipment_count = data["total_bonus_events_analyzed"]
        if demo_file in summary["demo_breakdown"]:
            summary["demo_breakdown"][demo_file][
                "equipment_purchases"
            ] = equipment_count

        summary["analysis_overview"]["total_equipment_purchases"] += equipment_count

        if ct_team in team_stats:
            team_stats[ct_team]["equipment_purchases"] += equipment_count
        if map_name in map_stats:
            map_stats[map_name]["equipment_purchases"] += equipment_count

    # Process kills analysis data
    for filename, data in all_results["kills_analysis"].items():
        demo_file = data["match_info"]["demo_file"]
        ct_team = data["match_info"]["ct_team"]
        map_name = data["match_info"]["map"]

        kills_count = data["summary"]["total_kills_with_purchased_weapons"]
        if demo_file in summary["demo_breakdown"]:
            summary["demo_breakdown"][demo_file][
                "kills_with_purchased_weapons"
            ] = kills_count

        summary["analysis_overview"][
            "total_kills_with_purchased_weapons"
        ] += kills_count

        if ct_team in team_stats:
            team_stats[ct_team]["kills"] += kills_count
        if map_name in map_stats:
            map_stats[map_name]["kills"] += kills_count

    # Process utility analysis data
    for filename, data in all_results["utility_analysis"].items():
        demo_file = data["match_info"]["demo_file"]
        ct_team = data["match_info"]["ct_team"]
        map_name = data["match_info"]["map"]

        utility_count = (
            data["summary"]["total_enemies_damaged"]
            + data["summary"]["total_enemies_flashed"]
        )
        if demo_file in summary["demo_breakdown"]:
            summary["demo_breakdown"][demo_file][
                "utility_impact_events"
            ] = utility_count

        summary["analysis_overview"]["total_utility_impact_events"] += utility_count

        if ct_team in team_stats:
            team_stats[ct_team]["utility_impact"] += utility_count
        if map_name in map_stats:
            map_stats[map_name]["utility_impact"] += utility_count

    summary["analysis_overview"]["total_demos_analyzed"] = len(demos_processed)
    summary["team_statistics"] = team_stats
    summary["map_statistics"] = map_stats

    return summary


def save_combined_output(all_results, summary):
    """Save the combined analysis results to a comprehensive output file"""

    # Create output directory
    os.makedirs("./combined_analysis", exist_ok=True)

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"combined_analysis_{timestamp}.json"
    output_path = os.path.join("./combined_analysis", output_filename)

    # Create comprehensive output structure
    combined_output = {
        "analysis_metadata": {
            "generated_at": datetime.now().isoformat(),
            "analysis_description": "Comprehensive CS2 Kill Bonus Analysis combining bonus events, equipment purchases, kills, and utility impact",
            "analysis_order": [
                "1. Bonus Analysis - Find CT team money bonus events (50-250 range)",
                "2. Equipment Analysis - Track equipment purchases in rounds following bonus events",
                "3. Kills Analysis - Analyze kills made with purchased weapons",
                "4. Utility Analysis - Analyze utility impact with purchased items",
            ],
            "data_sources": {
                "bonus_files_count": len(all_results["bonus_analysis"]),
                "equipment_files_count": len(all_results["equipment_analysis"]),
                "kills_files_count": len(all_results["kills_analysis"]),
                "utility_files_count": len(all_results["utility_analysis"]),
            },
        },
        "executive_summary": summary,
        "detailed_analysis": all_results,
    }

    # Save to file
    try:
        with open(output_path, "w") as f:
            json.dump(combined_output, f, indent=2)

        print(f"\n🎯 Combined analysis saved to: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error saving combined output: {e}")
        return None


def print_final_summary(summary):
    """Print a human-readable summary of the analysis results"""
    print("\n" + "=" * 80)
    print("FINAL ANALYSIS SUMMARY".center(80))
    print("=" * 80)

    overview = summary["analysis_overview"]
    print(f"\n📊 OVERALL STATISTICS:")
    print(f"   • Total demos analyzed: {overview['total_demos_analyzed']}")
    print(f"   • Total bonus events found: {overview['total_bonus_events']}")
    print(
        f"   • Total equipment purchases tracked: {overview['total_equipment_purchases']}"
    )
    print(
        f"   • Total kills with purchased weapons: {overview['total_kills_with_purchased_weapons']}"
    )
    print(
        f"   • Total utility impact events: {overview['total_utility_impact_events']}"
    )

    print(f"\n🏆 TEAM PERFORMANCE:")
    for team, stats in summary["team_statistics"].items():
        if team != "Unknown":
            print(f"   • {team}:")
            print(f"     - Bonus events: {stats['bonus_events']}")
            print(f"     - Equipment purchases: {stats['equipment_purchases']}")
            print(f"     - Kills with purchased weapons: {stats['kills']}")
            print(f"     - Utility impact events: {stats['utility_impact']}")

    print(f"\n🗺️  MAP BREAKDOWN:")
    for map_name, stats in summary["map_statistics"].items():
        if map_name != "Unknown":
            clean_map = map_name.replace("de_", "")
            print(f"   • {clean_map}:")
            print(f"     - Bonus events: {stats['bonus_events']}")
            print(f"     - Equipment purchases: {stats['equipment_purchases']}")
            print(f"     - Kills with purchased weapons: {stats['kills']}")
            print(f"     - Utility impact events: {stats['utility_impact']}")


def main():
    """Main orchestrator function"""

    print_banner("CS2 KILL BONUS ANALYSIS - FULL PIPELINE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {os.getcwd()}")

    # Check if demos directory exists
    if not os.path.exists("./demos"):
        print("❌ Error: ./demos directory not found!")
        print("Please ensure demo files (.dem) are placed in the ./demos/ directory")
        return 1

    # Check if demo files exist
    demo_files = glob.glob("./demos/*.dem")
    if not demo_files:
        print("❌ Error: No .dem files found in ./demos/ directory!")
        print("Please place CS2 demo files in the ./demos/ directory")
        return 1

    print(f"Found {len(demo_files)} demo files to analyze")

    total_start_time = time.time()

    try:
        # Phase 1: Bonus Analysis
        print_banner("PHASE 1: BONUS ANALYSIS")
        print("Finding CT team money bonus events (50-250 range)...")
        phase_start = time.time()

        bonus_finder.analyze_all_demos()

        phase_duration = time.time() - phase_start
        print_phase_complete("Bonus Analysis", phase_duration)

        # Phase 2: Equipment Analysis
        print_banner("PHASE 2: EQUIPMENT ANALYSIS")
        print("Analyzing equipment purchases in rounds following bonus events...")
        phase_start = time.time()

        equipment_finder.main()

        phase_duration = time.time() - phase_start
        print_phase_complete("Equipment Analysis", phase_duration)

        # Phase 3: Kills Analysis
        print_banner("PHASE 3: KILLS ANALYSIS")
        print("Analyzing kills made with purchased weapons...")
        phase_start = time.time()

        kills_compile.main()

        phase_duration = time.time() - phase_start
        print_phase_complete("Kills Analysis", phase_duration)

        # Phase 4: Utility Analysis
        print_banner("PHASE 4: UTILITY ANALYSIS")
        print("Analyzing utility impact with purchased items...")
        phase_start = time.time()

        util_compile.main()

        phase_duration = time.time() - phase_start
        print_phase_complete("Utility Analysis", phase_duration)

        # Phase 5: Combine Results
        print_banner("PHASE 5: COMBINING RESULTS")
        print("Loading and combining all analysis results...")
        phase_start = time.time()

        all_results = load_all_analysis_results()
        summary = generate_combined_summary(all_results)
        output_file = save_combined_output(all_results, summary)

        phase_duration = time.time() - phase_start
        print_phase_complete("Results Combination", phase_duration)

        # Display final summary
        print_final_summary(summary)

        total_duration = time.time() - total_start_time
        print(f"\n🎉 ANALYSIS COMPLETE! Total time: {total_duration:.2f} seconds")

        if output_file:
            print(f"\n📁 All results saved in respective directories:")
            print(f"   • ./bonus_analysis/")
            print(f"   • ./equipment_analysis/")
            print(f"   • ./kills_analysis/")
            print(f"   • ./utility_analysis/")
            print(f"   • ./combined_analysis/")
            print(f"\n📋 Combined report: {output_file}")

        return 0

    except Exception as e:
        print(f"\n❌ ANALYSIS FAILED: {e}")
        print(f"Error occurred after {time.time() - total_start_time:.2f} seconds")
        return 1


if __name__ == "__main__":
    sys.exit(main())
