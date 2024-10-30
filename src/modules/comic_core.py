import re
import difflib
from datetime import datetime

TODAY = datetime.now().strftime("%Y_%m_%d")

def is_similar_story(story1, story2, threshold=0.9):
    """
    Check if two stories are similar based on a similarity ratio.
    
    Args:
        story1 (str): The first story.
        story2 (str): The second story.
        threshold (float): The similarity threshold (default: 0.9).
    
    Returns:
        bool: True if the stories are similar, False otherwise.
    """
    similarity_ratio = difflib.SequenceMatcher(None, story1, story2).ratio()
    return similarity_ratio >= threshold

def parse_panel_summaries(comic_summary):
    """
    Parse the comic summary to extract individual panel summaries.
    
    Args:
        comic_summary (str): The full comic summary.
    
    Returns:
        list: A list of panel summaries.
    """
    panel_summaries = []
    summary_start = comic_summary.find("Summary:")
    if summary_start != -1:
        # New format with explicit Summary section
        summary_text = comic_summary[summary_start:]
        panels = re.findall(r'Panel \d+:(.*?)(?=Panel \d+:|$)', summary_text, re.DOTALL)
        for panel in panels:
            panel_summaries.append(panel.strip())
    else:
        # Original format
        panels = re.findall(r'Panel \d+:(.*?)(?=Panel \d+:|$)', comic_summary, re.DOTALL)
        for panel in panels:
            panel_summaries.append(panel.strip())
    
    # If we didn't find any summaries or found less than 3, add default ones
    while len(panel_summaries) < 3:
        panel_summaries.append("No summary available for this panel.")
    
    return panel_summaries[:3]  # Ensure we only return 3 summaries
