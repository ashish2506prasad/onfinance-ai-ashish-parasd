import re
import json
import pandas as pd
from pypdf import PdfReader
import google.generativeai as genai
from membedding import store_embedding 

class PDFContentExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.reader = PdfReader(pdf_path)
        self.full_text = ""
        self.full_text_without_toc = ""
        self.table_of_contents = None
        self.toc_dict = {}
        self.content_dict = {}
        
    def extract_full_text(self):
        """Extract text from all pages and combine into single string"""
        text_parts = []
        text_parts_without_toc = []
        table_of_contetns_5_pages = []
        for page in self.reader.pages:
            page_text = page.extract_text()
            if "TABLE OF CONTENTS" in page_text or "Table of Contents" in page_text:
                text_parts.append(page_text)
                table_of_contetns_5_pages.append(page_text)
            else:
                text_parts_without_toc.append(page_text)
                text_parts.append(page_text)
                if len(table_of_contetns_5_pages) < 5:
                    table_of_contetns_5_pages.append(page_text)

        self.full_text = "\n".join(text_parts)
        self.full_text_without_toc = "\n".join(text_parts_without_toc)
        self.table_of_contents = table_of_contetns_5_pages
        print("Text Extracted")
    
    def find_toc_text(self):
        text = ""
        for page in self.table_of_contents:
            if "......" in page:
                text = text.join(page)

        if "TABLE OF CONTENTS" in text:
            text = text.split("TABLE OF CONTENTS")[-1]
        elif "Table of Contents" in text:
            text = text.split("Table of Contents")[-1]
        return text
    
    def extract_toc_structure(self):
        """Extract table of contents structure"""
        toc_text = self.find_toc_text()
        if not toc_text:
            print("Could not find Table of Contents")
            return
        
        # Split into lines and clean
        lines = [line.strip() for line in toc_text.split('\n') if line.strip()]
        lines
        print("Table of Contents Lines:", lines)
        
        current_section = None
        
        for line in lines:
            # print("Checking:", line)
            if "SECTION" in line or "Section" in line or "section" in line:
                current_section = line.split(".")[0].strip()
                # print("Section Match:", current_section)
                self.toc_dict[current_section] = []
                continue
            
            else:
                chapter = line.split(".")[0].strip()
                print("Chapter Match:", chapter)
                self.toc_dict[current_section].append(chapter)

    
    def find_content_boundaries(self, text, start_pattern, end_pattern):
        """Find content between two patterns"""
        start_match = re.search(start_pattern, text, re.IGNORECASE)
        if not start_match:
            return ""
        
        content_start = start_match.end()
        end_match = re.search(end_pattern, text[content_start:], re.IGNORECASE)
        
        if end_match:
            content = text[content_start:content_start + end_match.start()]
        else:
            content = text[content_start:]
            
        return content.strip()
    
    def extract_tables(self, text):
        """Extract tables from text"""
        # Simple table detection - looks for consistent line patterns
        table_pattern = r"(?:\+[-+]+\+\n(?:\|[^\n]+\|\n)+\+[-+]+\+)"
        tables = re.finditer(table_pattern, text)
        
        table_dicts = []
        for table_match in tables:
            table_text = table_match.group()
            # Convert table text to DataFrame
            try:
                # Split into rows and clean up
                rows = [line.strip('|').split('|') for line in table_text.split('\n') 
                       if '|' in line and '-' not in line]
                if rows:
                    df = pd.DataFrame(rows[1:], columns=rows[0])
                    table_dicts.append(df.to_dict('records'))
            except Exception as e:
                print(f"Error converting table to DataFrame: {e}")
                
        return table_dicts if table_dicts else None
    
    def extract_content(self):
        """Extract content for sections and chapters"""
        # Get all section names for boundary detection
        all_sections = list(self.toc_dict.keys())
        
        for i, (section_name, chapters) in enumerate(self.toc_dict.items()):
            next_section = all_sections[i + 1] if i < len(all_sections) - 1 else None
            
            # Extract section content
            section_pattern = f"{section_name}"
            end_pattern = next_section if next_section else r"\Z"

            section_content = self.find_content_boundaries(self.full_text_without_toc, section_pattern, end_pattern)
            
            self.content_dict[section_name] = {
                "text": section_content,
                "chapters": {}
            }
            
            # Extract chapter content
            for j, chapter in enumerate(chapters):
                next_chapter = chapters[j + 1] if j < len(chapters) - 1 else next_section
                
                chapter_content = self.find_content_boundaries(
                    section_content,
                    re.escape(chapter),
                    re.escape(next_chapter) if next_chapter else r"\Z"
                )
                
                # Extract any tables in the chapter content
                tables = self.extract_tables(chapter_content)
                
                self.content_dict[section_name]["chapters"][chapter] = {
                    "text": chapter_content,
                    "tables": tables
                }
    
    def save_to_json(self, output_path):
        """Save extracted content to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.content_dict, f, ensure_ascii=False, indent=2)
    
    def process(self, output_path, dict_path):
        """Run full extraction process"""
        self.extract_full_text()
        self.extract_toc_structure()
        with open(dict_path, 'w', encoding='utf-8') as f:
            json.dump(self.toc_dict, f, ensure_ascii=False, indent=2)
        self.extract_content()
        self.save_to_json(output_path)
        
        return {
            "toc_structure": self.toc_dict,
            "content": self.content_dict
        }
    
def summarize_text(text):
    genai.configure(api_key="AIzaSyAJAU2aa-JO8aaHHOBuIan9aPeAJOlQLgI")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"summarize the text in 150 words: {text}")
    # print(response.text)
    return response.text

def process_sections(content, parent_key="", i=0):
    """Process sections and store embeddings"""
    for section_name, section_data in content.items():
        key = f"{parent_key}_{section_name}" if parent_key else section_name 

        if "text" in section_data and isinstance(section_data["text"], str):
            section_summary = summarize_text(section_data["text"])
            section_data["summary"] = section_summary  
            store_embedding(section_summary, f"{key}_summary_{i}")  

        if "chapters" in section_data and isinstance(section_data["chapters"], dict):
            process_sections(section_data["chapters"], key, i)

def main():
    import os

    parent_path = "testing"
    path = [os.path.join(parent_path + "\\input", f) for f in os.listdir(parent_path + "\\input") if f.endswith(".pdf")]
    for pdf_path in path:
        i = pdf_path.split("\\")[-1].split(".")[0]
        dict_path = os.path.join(parent_path + "\\output",f"toc_{i}.json")
        output_path = os.path.join(parent_path + "\\output",f"content_{i}.json")
        # print(output_path, dict_path)
        extractor = PDFContentExtractor(pdf_path)
        result = extractor.process(output_path, dict_path)

        with open(output_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
            
        process_sections(content, parent_key=i)

           

if __name__ == "__main__":
    main()