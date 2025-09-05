#!/usr/bin/env python3
"""
YouTube Transcript Fetcher

This script fetches transcripts from YouTube videos and saves them in two formats:
1. Timestamped format - with timestamps for each segment
2. Prose format - clean text with proper sentences and paragraphs

Usage:
    python get_subtitles.py
"""

import re
import sys
from typing import List, Dict, Any, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import argparse
import requests
from urllib.parse import urlparse, parse_qs


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various URL formats.
    
    Args:
        url: YouTube URL
        
    Returns:
        Video ID if found, None otherwise
    """
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def get_video_title(video_id: str) -> str:
    """
    Fetch YouTube video title using the video ID.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Video title or fallback to video_id if fetching fails
    """
    try:
        # Try to get title from YouTube's oembed API
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(oembed_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            title = data.get('title', '')
            if title:
                return title
    except Exception as e:
        print(f"Warning: Could not fetch video title: {e}")
    
    # Fallback to video_id if title fetching fails
    return video_id


def create_filename_from_title(title: str, video_id: str, language_code: str, file_type: str) -> str:
    """
    Create filename from video title (first 3 words) or fallback to video_id.
    
    Args:
        title: Video title
        video_id: Fallback video ID
        language_code: Language code
        file_type: Type of file (timestamped or prose)
        
    Returns:
        Formatted filename
    """
    # Clean the title and get first 3 words
    if title and title != video_id:
        # Remove special characters and split into words
        clean_title = re.sub(r'[^\w\s]', '', title)
        words = clean_title.split()[:3]
        if words:
            title_part = '_'.join(words).lower()
        else:
            title_part = video_id
    else:
        title_part = video_id
    
    return f"{title_part}_transcript_{file_type}_{language_code}.txt"


def get_available_languages(video_id: str) -> Dict[str, str]:
    """
    Get available transcript languages for a video.
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        Dictionary mapping language codes to language names
    """
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        languages = {}
        
        for transcript in transcript_list:
            languages[transcript.language_code] = transcript.language
        
        return languages
    except Exception as e:
        print(f"Error fetching available languages: {e}")
        return {}


def fetch_transcripts(video_id: str, language_codes: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch transcripts for all specified languages.
    
    Args:
        video_id: YouTube video ID
        language_codes: List of language codes to try
        
    Returns:
        Dictionary mapping language codes to transcript segments
    """
    api = YouTubeTranscriptApi()
    transcripts = {}
    
    for lang_code in language_codes:
        try:
            transcript = api.fetch(video_id, languages=[lang_code])
            # Convert FetchedTranscriptSnippet objects to dictionaries
            segments = []
            for snippet in transcript.snippets:
                segments.append({
                    'text': snippet.text,
                    'start': snippet.start,
                    'duration': snippet.duration
                })
            transcripts[lang_code] = segments
            print(f"✓ Successfully fetched transcript in {lang_code}")
        except Exception as e:
            # Extract just the main error message, not the full traceback
            error_msg = str(e).split('\n')[0] if '\n' in str(e) else str(e)
            print(f"Failed to fetch transcript in {lang_code}: {error_msg}")
            continue
    
    return transcripts


def format_timestamp(seconds: float) -> str:
    """
    Format seconds into HH:MM:SS format.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def create_timestamped_transcript(transcript: List[Dict[str, Any]]) -> str:
    """
    Create timestamped transcript format.
    
    Args:
        transcript: List of transcript segments
        
    Returns:
        Formatted timestamped transcript string
    """
    lines = []
    for segment in transcript:
        start_time = format_timestamp(segment['start'])
        text = segment['text'].strip()
        lines.append(f"[{start_time}] {text}")
    
    return '\n'.join(lines)


def create_prose_transcript(transcript: List[Dict[str, Any]]) -> str:
    """
    Create prose transcript with proper sentences and paragraphs.
    
    Args:
        transcript: List of transcript segments
        
    Returns:
        Formatted prose transcript string
    """
    # Join all text segments
    full_text = ' '.join(segment['text'] for segment in transcript)
    
    # Clean up the text
    full_text = re.sub(r'\s+', ' ', full_text)  # Replace multiple spaces with single space
    full_text = re.sub(r'\s+([.!?])', r'\1', full_text)  # Remove spaces before punctuation
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', full_text)
    
    # Group sentences into paragraphs (every 3-4 sentences)
    paragraphs = []
    current_paragraph = []
    
    for sentence in sentences:
        if sentence.strip():
            current_paragraph.append(sentence.strip())
            
            # Create paragraph every 3-4 sentences or at natural breaks
            if len(current_paragraph) >= 3:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []
    
    # Add remaining sentences as final paragraph
    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))
    
    return '\n\n'.join(paragraphs)


def save_transcript_files(transcript: List[Dict[str, Any]], video_id: str, language_code: str, video_title: str):
    """
    Save transcript in both timestamped and prose formats.
    
    Args:
        transcript: List of transcript segments
        video_id: YouTube video ID
        language_code: Language code used
        video_title: Video title for filename generation
    """
    # Create timestamped version
    timestamped_content = create_timestamped_transcript(transcript)
    timestamped_filename = create_filename_from_title(video_title, video_id, language_code, "timestamped")
    
    # Create prose version
    prose_content = create_prose_transcript(transcript)
    prose_filename = create_filename_from_title(video_title, video_id, language_code, "prose")
    
    try:
        # Save timestamped transcript
        with open(timestamped_filename, 'w', encoding='utf-8') as f:
            f.write(timestamped_content)
        print(f"✓ Timestamped transcript saved to: {timestamped_filename}")
        
        # Save prose transcript
        with open(prose_filename, 'w', encoding='utf-8') as f:
            f.write(prose_content)
        print(f"✓ Prose transcript saved to: {prose_filename}")
        
    except Exception as e:
        print(f"Error saving files: {e}")


def main():
    """Main function to run the transcript fetcher."""
    print("YouTube Transcript Fetcher")
    print("=" * 30)
    
    # Get YouTube URL from user
    while True:
        url = input("\nEnter YouTube video URL: ").strip()
        if not url:
            print("Please enter a valid URL.")
            continue
            
        video_id = extract_video_id(url)
        if not video_id:
            print("Invalid YouTube URL. Please try again.")
            continue
        break
    
    print(f"\nVideo ID: {video_id}")
    
    # Get video title
    print("Fetching video title...")
    video_title = get_video_title(video_id)
    print(f"Video title: {video_title}")
    
    # Get available languages
    print("\nFetching available languages...")
    languages = get_available_languages(video_id)
    
    if not languages:
        print("No transcripts available for this video.")
        return
    
    print("\nAvailable languages:")
    for code, name in languages.items():
        print(f"  {code}: {name}")
    
    # Get language preferences from user
    print("\nEnter language codes (comma-separated) or press Enter for auto-detection:")
    lang_input = input("Languages: ").strip()
    
    if lang_input:
        requested_languages = [lang.strip() for lang in lang_input.split(',')]
    else:
        # Auto-detect: try English first, then any available language
        requested_languages = ['en'] + list(languages.keys())
    
    # Fetch transcripts
    print(f"\nFetching transcripts in: {', '.join(requested_languages)}")
    transcripts = fetch_transcripts(video_id, requested_languages)
    
    if not transcripts:
        print("Failed to fetch transcripts in any of the requested languages.")
        return
    
    # Save transcript files for each language
    total_segments = 0
    for lang_code, transcript in transcripts.items():
        save_transcript_files(transcript, video_id, lang_code, video_title)
        total_segments += len(transcript)
    
    print(f"\nTranscript processing complete!")
    print(f"Languages processed: {', '.join(transcripts.keys())}")
    print(f"Total segments across all languages: {total_segments}")
    
    # Show duration from the first transcript (they should all be the same length)
    if transcripts:
        first_transcript = next(iter(transcripts.values()))
        if first_transcript:
            duration = format_timestamp(first_transcript[-1]['start'] + first_transcript[-1]['duration'])
            print(f"Duration: {duration}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
