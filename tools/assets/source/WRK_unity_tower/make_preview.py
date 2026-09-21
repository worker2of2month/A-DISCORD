"""Encode the verified native-geometry renders as a GIF and a scrubbable MP4."""
import subprocess
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
frames = [ROOT/'preview_frames'/f'{frame:04}.png' for frame in range(1,362,6)]
assert all(path.is_file() for path in frames)
assert min(path.stat().st_mtime for path in frames) > (ROOT/'verification_report.json').stat().st_mtime
palette = Image.open(frames[0]).convert('RGB').quantize(colors=192)
images = [Image.open(path).convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE) for path in frames]
images[0].save(ROOT/'Unity_tower_partial_collapse.gif',save_all=True,append_images=images[1:],duration=200,loop=0,optimize=False)
concat = ROOT/'preview.ffconcat'
concat.write_text('ffconcat version 1.0\n'+''.join(f"file 'preview_frames/{path.name}'\nduration 0.2\n" for path in frames)+f"file 'preview_frames/{frames[-1].name}'\n")
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),
                '-vf','fps=30','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',
                str(ROOT/'Unity_tower_partial_collapse.mp4')],check=True)
concat.unlink()
print('Encoded 61 verified preview frames; Blender geometry only, no engine particles.')
