#!/bin/bash

# 定义一个包含指令的数组
instructions=( "play Taylor Swift Love Story" "Play the song Shape of You" "Play the album  30 from Adele" "play my favorite playlist" "Play some music from JJ lin" "Play a random album from  Jay chou" "Play a song about sunny day" "Play a happy song" "I want some jazz music" "Play the music i liked" "Put the current playing song into my favorite playlist" "Remove this song from my playlist" "Download this song to my phone" "Put this song into my pop music playlist" "Enable single song loop" "Play all the songs in order" "Loop playing this playlist" "Find a different version of this song" "Watch the mv of this song" "Remove the love story from my playlist" "Enble the hifi mode" "Who sings this song" "Check the album of this song" "Check the user comments about this song" "Show the lyrics" "Check the current playlist" "Open the reccent playlist" "Subscribe the singer of this song" "Find another popular song by this singer" "Check all the albums by this singer" "Play the newest song by the singer" "Post a comment, quote amazing music on this song")

# 遍历指令数组
for instruction in "${instructions[@]}"
do
    echo "执行指令: $instruction"
    # 调用Python脚本并传递指令
    python run.py --task_instruction "$instruction"
done

echo "所有指令执行完毕"