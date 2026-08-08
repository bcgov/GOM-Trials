//
//  NumericFieldBridge.h
//  gomapp
//
//  Created by Kiri Daust on 2026-08-06.
//

#ifndef NumericFieldBridge_h
#define NumericFieldBridge_h

#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface NumericFieldBridge : UIView <UITextFieldDelegate>

@property (nonatomic, strong, readonly) UITextField *textField;

- (instancetype)initDecimal:(BOOL)decimal;

// Text

- (NSString *)text;
- (void)setText:(NSString *)text;

- (void)setPlaceholder:(NSString *)placeholder;

// Focus

- (BOOL)becomeFirstResponderField;
- (BOOL)resignFirstResponderField;

// State
- (BOOL)isFirstResponder;
- (BOOL)isVisible;
- (void)donePressed;

// Layout helper

- (void)setFrameX:(CGFloat)x
                y:(CGFloat)y
            width:(CGFloat)width
           height:(CGFloat)height;

- (void)setKivyFrameX:(CGFloat)x
                    y:(CGFloat)y
                width:(CGFloat)width
               height:(CGFloat)height;

- (void)donePressed;
- (void)show;
- (void)hide;
- (CGFloat)parentHeight;
@end

NS_ASSUME_NONNULL_END

#endif /* NumericFieldBridge_h */
