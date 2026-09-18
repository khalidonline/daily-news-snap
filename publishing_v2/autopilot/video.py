"""One atomic video delivery keeps attributed editorial images with their credits."""
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def _run(arguments):
    try:
        return subprocess.run(arguments, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=180).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('story_video_processing_failed: ' + type(error).__name__) from None


def _validate_stream(probe, duration):
    streams = probe.get('streams', [])
    if len(streams) != 1:
        raise ValueError('story_video_requires_one_silent_video_stream')
    stream = streams[0]
    expected = {'codec_type':'video', 'codec_name':'h264', 'pix_fmt':'yuv420p',
                'width':1080, 'height':1920, 'avg_frame_rate':'30/1'}
    if any(stream.get(key) != value for key, value in expected.items()):
        raise ValueError('story_video_format_mismatch')
    try:
        correct = (int(stream['nb_read_frames']) == duration*30
                   and abs(float(stream['duration'])-duration) < 0.02
                   and abs(float(probe['format']['duration'])-duration) < 0.02)
    except (KeyError, TypeError, ValueError):
        correct = False
    if not correct:
        raise ValueError('story_video_duration_or_frame_count_mismatch')


def _check_frame(source, decoded):
    with Image.open(source) as original, Image.open(decoded) as actual:
        if original.size != (1080,1920) or actual.size != original.size:
            raise ValueError('video_frame_dimensions_mismatch')
        difference = ImageChops.difference(original.convert('RGB'), actual.convert('RGB'))
        # Account for H.264/chroma subsampling without accepting blank, wrong,
        # reordered, or materially altered frames. Reviewer sees decoded pixels.
        if sum(ImageStat.Stat(difference).mean)/3 > 8:
            raise ValueError('video_frame_mismatch')


def compile_story(paths, outputdir):
    """Return (delivery_spec, decoded_review_paths) after verifying the exact MP4.

    Snapchat Story constraint: 5–60 seconds, at least 540×960 pixels.
    https://developers.snap.com/marketing-api/Public-Profile-API/ProfileAssetManagement
    """
    paths = [Path(path) for path in paths]
    if len(paths) > 5:
        raise ValueError('attributed_video_requires_at_most_four_editorial_cards')
    if len(paths) < 3:
        raise ValueError('attributed_video_requires_at_least_two_editorial_cards')
    for path in paths:
        with Image.open(path) as frame:
            if frame.format != 'JPEG' or frame.size != (1080,1920) or getattr(frame,'n_frames',1) != 1:
                raise ValueError('story_video_requires_1080x1920_jpeg_frames')
            frame.verify()
    durations = [10]*(len(paths)-1)+[15]
    duration = sum(durations)
    output = Path(outputdir)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.story-video-', dir=output) as scratch:
        temporary = Path(scratch)
        manifest = ['ffconcat version 1.0']
        for index, (source, seconds) in enumerate(zip(paths,durations)):
            name = f'input-{index:02d}.jpg'
            shutil.copyfile(source,temporary/name)
            manifest.extend([f"file '{name}'",f'duration {seconds}'])
        manifest.append(f"file 'input-{len(paths)-1:02d}.jpg'")
        listing = temporary/'frames.ffconcat'
        listing.write_text('\n'.join(manifest)+'\n',encoding='utf-8')
        movie = temporary/'story.mp4'
        _run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y',
              '-threads','1','-filter_threads','1','-f','concat','-safe','1','-i',str(listing),
              '-map','0:v:0','-an','-vf','fps=30,format=yuv420p','-frames:v',str(duration*30),
              '-c:v','libx264','-preset','ultrafast','-tune','stillimage','-crf','18','-threads','1',
              '-map_metadata','-1','-map_chapters','-1','-fflags','+bitexact','-flags:v','+bitexact',
              '-movflags','+faststart',str(movie)])
        probe = json.loads(_run(['ffprobe','-v','error','-count_frames','-show_streams',
                                '-show_format','-of','json',str(movie)]))
        _validate_stream(probe,duration)
        elapsed, midpoints = 0, []
        for seconds in durations:
            midpoints.append(int((elapsed+seconds/2)*30))
            elapsed += seconds
        selection = '+'.join(f'eq(n\\,{point})' for point in midpoints)
        _run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-threads','1',
              '-filter_threads','1','-i',str(movie),'-map','0:v:0','-vf','select='+selection,
              '-vsync','0','-frames:v',str(len(paths)),'-start_number','0',
              '-threads','1',str(temporary/'review-%02d.png')])
        reviews = [temporary/f'review-{index:02d}.png' for index in range(len(paths))]
        for original, review in zip(paths,reviews):
            _check_frame(original,review)
        specification = {'kind':'video','filename':'story.mp4',
            'sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),
            'frame_sha256':[hashlib.sha256(path.read_bytes()).hexdigest() for path in reviews],
            'duration_seconds':duration}
        for review in reviews:
            review.replace(output/review.name)
        movie.replace(output/'story.mp4')
    return specification, [output/f'review-{index:02d}.png' for index in range(len(paths))]
