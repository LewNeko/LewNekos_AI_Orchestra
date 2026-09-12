
```markdown
# Python Environment Commands

1. Go to the project  
   `cd <project>`

2. Create an isolated environment  
   `uv venv`  
   `# pip equivalent: python -m venv .venv`

3. Install what the project needs  
   `uv pip install <package>`  
   `# pip equivalent: .venv\Scripts\python -m pip install <package>`

4. Activate It  
   `# Command Prompt: .venv\Scripts\activate.bat`  
   `# PowerShell: .\.venv\Scripts\Activate.ps1`  
   You should see `(.venv)` at the leftmost part of the terminal.

5. Run the project  
   `uv run python <file.py>`  
   `# pip/venv equivalent: activate .venv, then python <file.py>`

6. Check the environment  
   `uv pip list`  
   `uv run python --version`  
   `# pip equivalent: python -m pip list`  
   `#                python --version`

7. Save dependencies  
   `uv pip freeze > requirements.txt`  
   `# pip equivalent: .venv\Scripts\python -m pip freeze > requirements.txt`

8. Deactivate when finished  
   `# any: deactivate`

9. TEST IT  
   `# in terminal: python -c "import <test>; print('Environment OK')"`  
   You should see `Environment OK`.

10. If `pip` isn't working correctly  
    `# First, make sure the environment is activated.`  
    `.venv\Scripts\activate.bat`

    `# Check which pip is being used:`  
    `where pip`

    `# The .venv path should appear first:`  
    `C:\...\project\.venv\Scripts\pip.exe`

    `# If pip is missing from the environment:`  
    `python -m ensurepip --upgrade`

    `# Then check again:`  
    `where pip`

    `# You can also bypass the pip command entirely:`  
    `python -m pip --version`
```
