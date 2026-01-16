
import flet as ft
import os
import threading
from pdf_redactor import RedactorConfig, load_pdf, ocr_pdf, run_redaction, save_redactions_to_file, save_redactions_to_relative_file

class PDFRedactorGUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PDF Redactor"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.window_width = 800
        self.page.window_height = 900
        self.page.padding = 40
        
        self.selected_files = []
        self.selected_dir = None
        
        self.setup_ui()

    def setup_ui(self):
        # Header
        self.header = ft.Column([
            ft.Text("PDF Redactor", size=48, weight=ft.FontWeight.BOLD),
            ft.Text("Professional Privacy Protection", size=16, color=ft.Colors.GREY_400),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        # File Selection Section
        self.file_picker = ft.FilePicker(on_result=self.on_file_result)
        self.dir_picker = ft.FilePicker(on_result=self.on_dir_result)
        self.page.overlay.extend([self.file_picker, self.dir_picker])

        self.file_display = ft.Text("No files selected", color=ft.Colors.GREY_400)
        
        self.selection_row = ft.Row([
            ft.ElevatedButton("Select PDF Files", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: self.file_picker.pick_files(allow_multiple=True, allowed_extensions=["pdf"])),
            ft.ElevatedButton("Select Directory", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: self.dir_picker.get_directory_path()),
        ], alignment=ft.MainAxisAlignment.CENTER)

        # Redaction Options (Toggles)
        self.toggles = {
            "email": ft.Switch(label="Email Addresses", value=True),
            "link": ft.Switch(label="Links", value=False),
            "phonenumber": ft.Switch(label="Phone Numbers", value=True),
            "date": ft.Switch(label="Dates", value=False),
            "timestamp": ft.Switch(label="Timestamps", value=False),
            "iban": ft.Switch(label="IBANs", value=True),
            "bic": ft.Switch(label="BICs", value=True),
            "barcode": ft.Switch(label="Barcodes", value=False),
            "qrcode": ft.Switch(label="QR Codes", value=False),
        }

        options_grid = ft.ResponsiveRow([
            ft.Column([val], col={"sm": 6, "md": 4}) for val in self.toggles.values()
        ], spacing=10)

        # Custom Settings
        self.custom_mask = ft.TextField(label="Custom Masks (comma separated)", placeholder="e.g. John Doe, SecretKey")
        self.replacement_text = ft.TextField(label="Replacement Text", placeholder="[REDACTED]")
        
        self.fill_color = ft.Dropdown(
            label="Fill Color",
            value="black",
            options=[
                ft.dropdown.Option("black"),
                ft.dropdown.Option("white"),
                ft.dropdown.Option("red"),
                ft.dropdown.Option("green"),
                ft.dropdown.Option("blue"),
            ]
        )

        # Preview & Process
        self.preview_toggle = ft.Switch(label="Preview before applying", value=False)
        self.process_button = ft.ElevatedButton(
            "Start Redaction", 
            icon=ft.Icons.PLAY_ARROW_ROUNDED, 
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
            on_click=self.start_processing
        )
        
        self.progress_bar = ft.ProgressBar(width=700, visible=False)
        self.status_text = ft.Text("", weight=ft.FontWeight.W_500)

        # Layout Assembly
        self.page.add(
            ft.Column([
                self.header,
                ft.Divider(height=40, color=ft.Colors.TRANSPARENT),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Source Selection", size=20, weight=ft.FontWeight.BOLD),
                            self.selection_row,
                            ft.Container(self.file_display, alignment=ft.alignment.center, padding=10),
                        ]),
                        padding=20
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Redaction Targets", size=20, weight=ft.FontWeight.BOLD),
                            options_grid,
                        ]),
                        padding=20
                    )
                ),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD),
                            ft.Row([self.custom_mask, self.replacement_text], spacing=20),
                            ft.Row([self.fill_color, self.preview_toggle], spacing=20),
                        ]),
                        padding=20
                    )
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Column([
                    self.process_button,
                    self.status_text,
                    self.progress_bar,
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            ], scroll=ft.ScrollMode.ADAPTIVE)
        )

    def on_file_result(self, e: ft.FilePickerResultEvent):
        if e.files:
            self.selected_files = [f.path for f in e.files]
            self.selected_dir = None
            self.file_display.value = f"Selected {len(self.selected_files)} files"
            self.file_display.color = ft.Colors.BLUE_400
        else:
            self.selected_files = []
            self.file_display.value = "No files selected"
            self.file_display.color = ft.Colors.GREY_400
        self.page.update()

    def on_dir_result(self, e: ft.FilePickerResultEvent):
        if e.path:
            self.selected_dir = e.path
            self.selected_files = []
            self.file_display.value = f"Selected Directory: {self.selected_dir}"
            self.file_display.color = ft.Colors.GREEN_400
        else:
            self.selected_dir = None
            self.file_display.value = "No directory selected"
            self.file_display.color = ft.Colors.GREY_400
        self.page.update()

    def start_processing(self, _):
        if not self.selected_files and not self.selected_dir:
            self.page.snack_bar = ft.SnackBar(ft.Text("Please select files or a directory first!"))
            self.page.snack_bar.open = True
            self.page.update()
            return

        self.process_button.disabled = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0
        self.status_text.value = "Initializing..."
        self.page.update()

        # Run redaction in a separate thread to keep UI responsive
        threading.Thread(target=self.process_thread, daemon=True).start()

    def process_thread(self):
        try:
            masks = [m.strip() for m in self.custom_mask.value.split(",")] if self.custom_mask.value else []
            
            config = RedactorConfig(
                email=self.toggles["email"].value,
                link=self.toggles["link"].value,
                phonenumber=self.toggles["phonenumber"].value,
                date=self.toggles["date"].value,
                timestamp=self.toggles["timestamp"].value,
                iban=self.toggles["iban"].value,
                bic=self.toggles["bic"].value,
                barcode=self.toggles["barcode"].value,
                qrcode=self.toggles["qrcode"].value,
                mask=masks,
                text=self.replacement_text.value or None,
                color=self.fill_color.value,
                preview=self.preview_toggle.value,
            )

            files_to_process = []
            if self.selected_dir:
                files_to_process = [os.path.join(self.selected_dir, f) for f in os.listdir(self.selected_dir) if f.lower().endswith(".pdf")]
            else:
                files_to_process = self.selected_files

            total = len(files_to_process)
            for i, file_path in enumerate(files_to_process):
                filename = os.path.basename(file_path)
                self.status_text.value = f"Processing {i+1}/{total}: {filename}"
                self.progress_bar.value = (i) / total
                self.page.update()

                # Core redaction logic
                pdf_doc = load_pdf(file_path)
                text_pages = ocr_pdf(pdf_doc)
                pdf_doc = run_redaction(file_path, text_pages, pdf_doc, config)
                
                # Save
                out_path = "{0}_{2}{1}".format(*os.path.splitext(file_path) + ("redacted",))
                pdf_doc.ez_save(out_path)
                pdf_doc.close()

            self.status_text.value = f"Success! Processed {total} files."
            self.status_text.color = ft.Colors.GREEN_400
            self.progress_bar.value = 1.0
            
        except Exception as e:
            self.status_text.value = f"Error: {str(e)}"
            self.status_text.color = ft.Colors.RED_400
        
        self.process_button.disabled = False
        self.page.update()

def main():
    ft.app(target=PDFRedactorGUI)

if __name__ == "__main__":
    main()
