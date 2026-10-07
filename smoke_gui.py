import app

ui = app.AgentQAStudio()
ui.update_idletasks()
print(ui.title())
print(len(ui.cases))
ui.destroy()
