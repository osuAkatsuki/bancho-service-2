create table if not exists tokens (
    token_id varchar(64) not null primary key,
    user_id int not null,
    username varchar(255) not null,
    privileges int not null,
    whitelist int not null,
    kicked tinyint(1) not null,
    login_time int not null,
    ping_time int not null,
    utc_offset int not null,
    tournament tinyint(1) not null,
    block_non_friends_dm tinyint(1) not null,
    spectating_token_id varchar(64) null,
    spectating_user_id int null,
    latitude float not null,
    longitude float not null,
    ip varchar(255) not null,
    country int not null,
    away_message varchar(255) null,
    match_id int null,
    last_np_beatmap_id int null,
    last_np_mods int null,
    last_np_accuracy float null,
    silence_end_time int not null,
    protocol_version int not null,
    spam_rate int not null,
    action_id int not null,
    action_text varchar(255) not null,
    action_md5 varchar(32) not null,
    action_beatmap_id int not null,
    action_mods int not null,
    mode int not null,
    relax tinyint(1) not null,
    autopilot tinyint(1) not null,
    ranked_score bigint not null,
    accuracy float not null,
    playcount int not null,
    total_score bigint not null,
    global_rank int not null,
    pp int not null
);

create table if not exists streams (
    name varchar(255) not null primary key
);

create table if not exists stream_tokens (
    stream_name varchar(255) not null,
    token_id varchar(64) not null,
    primary key (stream_name, token_id)
);

create table if not exists token_buffers (
    buffer_id int not null auto_increment primary key,
    token_id varchar(64) not null,
    buffer json not null
);

create table if not exists channels (
    name varchar(255) not null primary key,
    description varchar(255) not null,
    public_read tinyint(1) not null,
    public_write tinyint(1) not null,
    moderated tinyint(1) not null,
    instance tinyint(1) not null
);

create table if not exists channel_tokens (
    channel_name varchar(255) not null,
    token_id varchar(64) not null,
    primary key (channel_name, token_id)
);