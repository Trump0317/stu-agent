"""read_file / write_file 工具单元测试

审核人: Trump
审核日期: 2026-06-07
审核状态: [已通过]
"""

import pytest
from src.tools.file_tools import ReadFileTool, WriteFileTool


class TestReadFileTool:
    def test_schema(self):
        tool = ReadFileTool()
        s = tool.to_openai_schema()
        assert s["function"]["name"] == "read_file"
        assert "path" in str(s["function"]["parameters"])

    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        tool = ReadFileTool()
        result = await tool.execute(path=str(f))
        assert result.success is True
        assert result.content == "hello world"

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        tool = ReadFileTool()
        result = await tool.execute(path="/nonexistent/file.txt")
        assert result.success is False
        assert result.error is not None


class TestWriteFileTool:
    def test_schema(self):
        tool = WriteFileTool()
        s = tool.to_openai_schema()
        assert s["function"]["name"] == "write_file"
        assert "path" in str(s["function"]["parameters"])
        assert "content" in str(s["function"]["parameters"])

    @pytest.mark.asyncio
    async def test_write_and_read(self, tmp_path):
        """写入后 read_file 可读到相同内容"""
        f = tmp_path / "output.txt"
        tool = WriteFileTool()
        result = await tool.execute(path=str(f), content="写入内容")
        assert result.success is True
        # 用 ReadFileTool 回读验证闭环
        read_result = await ReadFileTool().execute(path=str(f))
        assert read_result.success is True
        assert read_result.content == "写入内容"

    @pytest.mark.asyncio
    async def test_overwrite(self, tmp_path):
        f = tmp_path / "output.txt"
        f.write_text("旧内容", encoding="utf-8")
        tool = WriteFileTool()
        result = await tool.execute(path=str(f), content="新内容")
        assert result.success is True
        read_result = await ReadFileTool().execute(path=str(f))
        assert read_result.content == "新内容"

    @pytest.mark.asyncio
    async def test_write_to_readonly_path(self, tmp_path):
        """写入只读路径返回 success=False"""
        tool = WriteFileTool()
        result = await tool.execute(path="/readonly/nope.txt", content="x")
        assert result.success is False
