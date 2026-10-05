"""What disc-ship sends is the movie folder, or a lone feature -- never a hidden directory.

It took the first directory under transcoded/ for the movie folder, in
whatever order the filesystem listed them, and any folder outranked a bare
file.
"""


def test_a_lone_feature_ships_past_a_hidden_directory(script, tmp_path):
    ship = script("disc-ship")
    transcoded = tmp_path / "transcoded"
    (transcoded / ".disc-pipeline-partial").mkdir(parents=True)
    feature = transcoded / "Film (1997).mkv"
    feature.write_bytes(b"complete")

    assert ship._source(tmp_path) == feature


def test_the_movie_folder_ships_past_a_hidden_directory(script, tmp_path):
    ship = script("disc-ship")
    transcoded = tmp_path / "transcoded"
    (transcoded / ".disc-pipeline-partial").mkdir(parents=True)
    movie = transcoded / "Film (1997)"
    movie.mkdir()

    assert ship._source(tmp_path) == movie
