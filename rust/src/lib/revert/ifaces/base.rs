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
        // If desired switch from static IP to auto IP without mentioning
        // `address` property, the auto-generated revert state will not
        // contains `address` property. In this case, if we noticed
        // static/auto flipping, we clone current IP state to revert.
        if desired.ipv4.as_ref().map(|i| i.is_auto()) == Some(true)
            && current.ipv4.as_ref().map(|i| !i.is_auto()) == Some(true)
        {
            self.ipv4.clone_from(&current.ipv4);
        }

        if desired.ipv6.as_ref().map(|i| i.is_auto()) == Some(true)
            && current.ipv6.as_ref().map(|i| !i.is_auto()) == Some(true)
        {
            self.ipv6.clone_from(&current.ipv6);
        }
        self.ipv4.as_mut().and_then(|i| i.sanitize(false).ok());
        self.ipv6.as_mut().and_then(|i| i.sanitize(false).ok());
    }
}
