use std::convert::TryFrom;
use std::marker::PhantomData;
use std::str::FromStr;

use serde::{de, de::Visitor, Deserializer};

// This function is inspired by https://serde.rs/string-or-struct.html
pub(crate) fn option_u16_or_string<'de, D>(
    deserializer: D,
) -> Result<Option<u16>, D::Error>
where
    D: Deserializer<'de>,
{
    struct IntegerOrString(PhantomData<fn() -> Option<u16>>);

    impl<'de> Visitor<'de> for IntegerOrString {
        type Value = Option<u16>;

        fn expecting(
            &self,
            formatter: &mut std::fmt::Formatter,
        ) -> std::fmt::Result {
            formatter.write_str("integer or string")
        }

        fn visit_str<E>(self, value: &str) -> Result<Option<u16>, E>
        where
            E: de::Error,
        {
            if let Some(prefix_len) = value.strip_prefix("0x") {
                u16::from_str_radix(prefix_len, 16)
                    .map_err(de::Error::custom)
                    .map(Some)
            } else {
                FromStr::from_str(value)
                    .map_err(de::Error::custom)
                    .map(Some)
            }
        }

        fn visit_u64<E>(self, value: u64) -> Result<Option<u16>, E>
        where
            E: de::Error,
        {
            TryFrom::try_from(value)
                .map_err(de::Error::custom)
                .map(Some)
        }
    }

    deserializer.deserialize_any(IntegerOrString(PhantomData))
}
