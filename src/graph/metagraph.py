from llm.llm_client import LLMClient
from database.pgvector import PGVector
import os
import json
import asyncio

class Metagraph:
    """
    An overlay graph that shows high-level relationships between larger components of the text (chapters, sections, paragraphs, etc.)
    Mostly serves to make navigating the document and graph easier for a human.
    """
    def __init__(self, llm_client: LLMClient, db_client: PGVector):
        self.llm_client = llm_client
        self.db_client = db_client

    async def summarize_structure(self, structure_id: int):
        atoms = await self.db_client.get_atoms_in_structure(structure_id)
        structure_atoms = {}
        for atom in atoms:
            structure_atoms[atom["id"]] = {"type": atom["classification"], "text": atom["text"]}

        text = str(structure_atoms)
        summary = await self.llm_client.get_summary(text)
        try:
            await self.db_client.add_structure_summary(structure_id, summary)
            return summary
        except Exception as e:
            print(f"Error adding summary to database for structure {structure_id}: {e}")
            return None
        
    async def structure_summary_exists(self, structure_id: int):
        return await self.db_client.get_structure_summary(structure_id) is not None
    
    async def summarize_section(self, section: dict, chapter_title: str):
        # Summarize paragraphs sequentially
        paragraphs = await self.db_client.get_paragraphs_in_structure(section["id"])
        for paragraph in paragraphs:
            if not await self.structure_summary_exists(paragraph["id"]):
                print(f"Summarizing paragraph {paragraph['id']} in section {section.get('title', 'Untitled')}...")
                await self.summarize_structure(paragraph["id"])

        # Summarize the section itself
        if not await self.structure_summary_exists(section["id"]):
            print(f"Summarizing section {section.get('title', 'Untitled')} in chapter {chapter_title}...")
            await self.summarize_structure(section["id"])

    async def summarize_chapter(self, chapter: dict):
        # Summarize sections in parallel
        sections = await self.db_client.get_sections_in_structure(chapter["id"])
        
        section_tasks = [
            self.summarize_section(section, chapter.get("title", "Untitled")) for section in sections
        ]
        await asyncio.gather(*section_tasks)

        # Summarize the chapter itself
        if not await self.structure_summary_exists(chapter["id"]):
            print(f"Summarizing chapter {chapter.get('title', 'Untitled')}...")
            await self.summarize_structure(chapter["id"])

    async def construct_metagraph(self, document_id: int):
        print(f"Constructing metagraph for document {document_id}...")
        chapters = await self.db_client.get_chapters_in_document(document_id)
        
        chapter_tasks = [
            self.summarize_chapter(chapter) for chapter in chapters
        ]
        await asyncio.gather(*chapter_tasks)
        print("Metagraph construction complete.")
        
    
        
