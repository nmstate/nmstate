macro_rules! _connection_inner_string_member {
    ($self_struct: ident, $member: ident) => {
        $self_struct
            .connection
            .as_ref()
            .map(|conn| conn.$member.as_deref())
            .flatten()
    };
}

macro_rules! _from_map {
    ($map: ident, $remove: expr, $convert: expr) => {
        $map.remove($remove).map($convert).transpose()
    };
}
