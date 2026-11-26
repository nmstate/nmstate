// SPDX-License-Identifier: Apache-2.0

use crate::BaseInterface;

impl BaseInterface {
    pub(crate) fn generate_revert_extra(
        &mut self,
        desired: &Self,
        current: &Self,
    ) {
        if !desired.can_have_ip() && self.can_have_ip() {
            self.ipv4.clone_from(&current.ipv4);
            self.ipv6.clone_from(&current.ipv6);
        }
        // Disabling IP or switching from static to auto can discard IP
        // settings that the desired state omits. Restore the full IP config.
        if desired
            .ipv4
            .as_ref()
            .zip(current.ipv4.as_ref())
            .is_some_and(|(desired, current)| {
                (!desired.enabled && current.enabled)
                    || (desired.is_auto() && !current.is_auto())
            })
        {
            self.ipv4.clone_from(&current.ipv4);
        }

        if desired
            .ipv6
            .as_ref()
            .zip(current.ipv6.as_ref())
            .is_some_and(|(desired, current)| {
                (!desired.enabled && current.enabled)
                    || (desired.is_auto() && !current.is_auto())
            })
        {
            self.ipv6.clone_from(&current.ipv6);
        }
        self.ipv4.as_mut().and_then(|i| i.sanitize(false).ok());
        self.ipv6.as_mut().and_then(|i| i.sanitize(false).ok());
    }
}
